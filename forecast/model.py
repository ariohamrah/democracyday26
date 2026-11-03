"""Ridge margin model with strictly earlier-cycle model selection/calibration."""
import math
from collections import defaultdict
import numpy as np
from scipy.special import ndtr
from scipy.linalg import solve

BASE_FEATURES = ['lag_margin', 'prior_pres_margin', 'incumbent_difference',
                 'midterm_president', 'senate', 'lag_missing', 'aura_difference', 'aura_missing']
FULL_FEATURES = BASE_FEATURES + ['generic_margin','generic_present','poll_residual','poll_present']
ALPHAS = [1., 10., 100., 1000.]


def metrics(y, q):
    y, q = np.asarray(y), np.clip(np.asarray(q), 1e-8, 1-1e-8)
    if not len(y):
        return dict(n=0, brier=None, log_loss=None, accuracy=None, calibration=[])
    bins = []
    for low in np.arange(0, 1, .1):
        use = (q >= low) & (q < low + .1)
        if use.any():
            bins.append(dict(lower=round(float(low), 1), n=int(use.sum()),
                             predicted=float(q[use].mean()), observed=float(y[use].mean())))
    return dict(n=len(y), brier=float(np.mean((q-y)**2)),
                log_loss=float(-np.mean(y*np.log(q)+(1-y)*np.log(1-q))),
                accuracy=float(np.mean((q >= .5) == y)), calibration=bins)


class RidgeModel:
    """Standardized ridge with explicit contractions (portable across BLAS builds)."""
    def __init__(self, x, y, alpha):
        self.mean = np.mean(x,axis=0)
        self.scale = np.std(x,axis=0)
        self.scale[self.scale < 1e-12] = 1.
        self.intercept = float(np.mean(y))
        z = (x-self.mean)/self.scale
        gram = np.einsum('ni,nj->ij',z,z,optimize=False)
        rhs = np.einsum('ni,n->i',z,y-self.intercept,optimize=False)
        self.coef = solve(gram + alpha*np.eye(x.shape[1]),rhs,assume_a='pos')
        if not np.all(np.isfinite(self.coef)):
            raise ValueError('Nonfinite fitted coefficients')

    def predict(self, x):
        pred = self.intercept + np.einsum('ni,i->n',(x-self.mean)/self.scale,self.coef,optimize=False)
        if not np.all(np.isfinite(pred)):
            raise ValueError('Nonfinite predictions')
        return pred


def fit(x, y, alpha):
    return RidgeModel(x,y,alpha)


def select_alpha(x, y, years):
    """Expanding training folds, never random district rows."""
    cycles = sorted(set(years))
    folds = cycles[3:]
    if not folds:
        return 100.
    loss = {}
    for alpha in ALPHAS:
        errors = []
        for year in folds:
            train, test = years < year, years == year
            m = fit(x[train], y[train], alpha)
            # Equal cycle weight avoids the House count dominating year selection.
            errors.append(np.mean((m.predict(x[test]) - y[test]) ** 2))
        loss[alpha] = np.mean(errors)
    return min(loss, key=loss.get)


def residuals_before(x, y, years, alpha):
    """Nested earlier-cycle tuning prevents optimistic calibration residuals.

    ``alpha`` remains an API compatibility argument; the eventual full-training
    alpha must not influence models for earlier calibration folds.
    """
    pred, indices = [], []
    for year in sorted(set(years))[3:]:
        train, test = years < year, years == year
        fold_alpha = select_alpha(x[train], y[train], years[train])
        model = fit(x[train], y[train], fold_alpha)
        pred.extend(model.predict(x[test]))
        indices.extend(np.where(test)[0])
    ix = np.asarray(indices, dtype=int)
    return ix, y[ix] - np.asarray(pred)


def uncertainty(residuals, indices, rows):
    """Estimate marginal error and national/region covariance from earlier OOT errors."""
    if len(residuals) < 20:
        return dict(sigma_house=20., sigma_senate=20., national_sd=0., regional_sd=0.,
                    note='Insufficient earlier out-of-time residuals; conservative 20-point fallback')
    groups = defaultdict(list)
    by_chamber = defaultdict(list)
    for i, err in zip(indices, residuals):
        r = rows[i]
        groups[(int(r['year']), r['region'])].append(float(err))
        by_chamber[r['chamber']].append(float(err))
    years = sorted({year for year, region in groups})
    national = []
    regional = []
    for year in years:
        e = [err for (yr, region), errors in groups.items() if yr == year for err in errors]
        mean = float(np.mean(e))
        national.append(mean)
        for (yr, region), errors in groups.items():
            if yr == year:
                # Subtract sampling noise from regional mean variance below.
                regional.append((float(np.mean(errors)) - mean, len(errors)))
    rms = {c: max(3., float(np.sqrt(np.mean(np.square(v))))) for c, v in by_chamber.items()}
    national_var = max(0., float(np.mean(np.square(national))))
    residual_var = float(np.mean(np.square(residuals)))
    regional_var = max(0., float(np.mean([r*r-residual_var/n for r,n in regional])))
    cap = min(rms.values()) ** 2 * .8
    if national_var + regional_var > cap:
        factor = cap / (national_var + regional_var)
        national_var *= factor
        regional_var *= factor
    return dict(sigma_house=rms.get('House', 20.), sigma_senate=rms.get('Senate', 20.),
                national_sd=math.sqrt(national_var), regional_sd=math.sqrt(regional_var),
                calibration_cycles=years)


def train_predict(rows, targets, feature_names=BASE_FEATURES):
    x = np.asarray([[float(r[f]) for f in feature_names] for r in rows])
    y = np.asarray([float(r['margin']) for r in rows])
    years = np.asarray([int(r['year']) for r in rows])
    alpha = select_alpha(x, y, years)
    ix, residual = residuals_before(x, y, years, alpha)
    u = uncertainty(residual, ix, rows)
    m = fit(x, y, alpha)
    xt = np.asarray([[float(r[f]) for f in feature_names] for r in targets])
    mu = m.predict(xt)
    sigma = np.asarray([u['sigma_' + r['chamber'].lower()] for r in targets])
    q = ndtr(mu / sigma)
    coefficients = dict(zip(feature_names, map(float, m.coef / m.scale)))
    return q, mu, sigma, dict(alpha=alpha, uncertainty=u, coefficients=coefficients)


def backtest(rows, features=BASE_FEATURES, start=2016):
    forecasts = []
    for year in sorted({int(r['year']) for r in rows}):
        if year < start:
            continue
        train = [r for r in rows if int(r['year']) < year]
        test = [r for r in rows if int(r['year']) == year]
        q, mu, sigma, info = train_predict(train, test, features)
        for r, p, center, sd in zip(test, q, mu, sigma):
            forecasts.append(dict(year=year, race_id=r['race_id'], chamber=r['chamber'],
                                  q=float(p), margin=float(r['margin']), predicted_margin=float(center),
                                  sigma=float(sd), outcome=int(float(r['margin']) > 0),
                                  competitive=abs(float(r['prior_pres_margin'])) <= 10,
                                  lag_missing=bool(r['lag_missing']),
                                  poll_present=bool(r.get('poll_present',0)),
                                  historical_poll_coverage='polled' if r.get('poll_present',0) else 'unpolled_or_unavailable_archive', alpha=info['alpha']))
    return forecasts
