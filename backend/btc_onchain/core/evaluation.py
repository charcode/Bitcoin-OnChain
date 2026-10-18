"""Comparison-only measurements; no evaluation data flows back into inference."""
import asyncio
import json
import math
import statistics
import time
import aiosqlite


def compare(state, poller, now=None):
    now = time.time() if now is None else now
    legacy = state.latest_price_now().model_dump()
    legacy['status'] = getattr(state.rnr, 'last_status', 'warming_up')
    candidate = {**state.rnr.candidate, 't': state.rnr.candidate_ts}
    quotes = poller.snapshot(now) if poller else {'sources': {}, 'median': {'price': None, 'ts': None, 'source_count': 0}}
    reference = quotes['median']
    for model in (legacy, candidate):
        age = now - model.get('t', 0)
        price = model.get('price')
        model['fresh'] = price is not None and math.isfinite(price) and price > 0 and 0 <= age <= 30 and model.get('status') in ('ok', 'experimental')
        model['age_sec'] = max(0, age)
        model['error_usd'] = model['error_pct'] = None
        if model['fresh'] and reference.get('price') and abs(model['t'] - reference['ts']) <= 45:
            error = price - reference['price']
            model['error_usd'] = error
            model['error_pct'] = 100 * error / reference['price']
    return {'t': now, 'mode': 'shadow', 'primary_model': 'legacy', 'legacy': legacy,
            'candidate': candidate, 'reference': reference, 'sources': quotes['sources'],
            'comparison_only': True, 'error_definition': 'estimate minus fresh USD exchange median'}


def metrics(rows):
    if not rows:
        return {'n': 0, 'bias_usd': None, 'bias_pct': None, 'mae_usd': None, 'mape_pct': None,
                'p95_abs_pct': None, 'band_coverage_pct': None}
    abs_pct = sorted(abs(r[5]) for r in rows)
    band_rows = [r for r in rows if r[6] is not None and r[7] is not None]
    return {'n': len(rows), 'bias_usd': statistics.mean(r[4] for r in rows),
            'bias_pct': statistics.mean(r[5] for r in rows),
            'mae_usd': statistics.mean(abs(r[4]) for r in rows),
            'mape_pct': statistics.mean(abs_pct),
            'p95_abs_pct': abs_pct[min(len(rows)-1, math.ceil(.95*len(rows))-1)],
            'band_coverage_pct': 100*sum(r[6] <= r[3] <= r[7] for r in band_rows)/len(band_rows) if band_rows else None}


class EvaluationRecorder:
    def __init__(self, state, poller, path):
        self.state, self.poller, self.path = state, poller, path
        self.last_reference_ts = None
        self.stats = {'n': 0, 'paired_n': 0, 'models': {}, 'paired_models': {}, 'status': 'warming_up'}

    async def run(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS model_evaluation(
                ts REAL NOT NULL, model TEXT NOT NULL, estimate REAL, reference REAL,
                error REAL, error_pct REAL, lower REAL, upper REAL,
                model_ts REAL, version TEXT, quality TEXT, PRIMARY KEY(ts,model))''')
            await db.commit()
        while True:
            try:
                await self.tick()
            except Exception:
                self.stats = {**self.stats, 'status': 'storage_unavailable'}
            await asyncio.sleep(30)

    async def tick(self):
        snap = compare(self.state, self.poller)
        ref = snap['reference']
        async with aiosqlite.connect(self.path) as db:
            if ref.get('ts') and ref['ts'] != self.last_reference_ts:
                for model in ('legacy', 'candidate'):
                    d = snap[model]
                    if d.get('error_usd') is None: continue
                    await db.execute('INSERT OR IGNORE INTO model_evaluation VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (ref['ts'], model, d['price'], ref['price'], d['error_usd'], d['error_pct'], d.get('lower'), d.get('upper'), d['t'], d.get('version', 'legacy'), json.dumps({'status': d.get('status'), 'sources': snap['sources'], 'matched_outputs': d.get('matched_outputs'), 'anchor_count': d.get('anchor_count')})))
                self.last_reference_ts = ref['ts']
            await db.execute('DELETE FROM model_evaluation WHERE ts < ?', (time.time()-14*86400,))
            await db.commit()
            rows = await (await db.execute('SELECT * FROM model_evaluation WHERE ts >= ? ORDER BY ts', (time.time()-86400,))).fetchall()
        times = {}
        for row in rows: times.setdefault(row[0], set()).add(row[1])
        paired = {ts for ts, models in times.items() if len(models) == 2}
        self.stats = {'n': len(times), 'paired_n': len(paired), 'window_hours': 24,
            'first_ts': rows[0][0] if rows else None, 'last_ts': rows[-1][0] if rows else None,
            'status': 'accumulating_unvalidated', 'updated_at': time.time(),
            'models': {m: metrics([r for r in rows if r[1] == m]) for m in ('legacy', 'candidate')},
            'paired_models': {m: metrics([r for r in rows if r[1] == m and r[0] in paired]) for m in ('legacy', 'candidate')}}
