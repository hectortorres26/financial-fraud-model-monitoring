"""Proyecto 2104: ejecucion reproducible sobre los CSV originales de DataCamp."""
from pathlib import Path
import calendar
import hashlib
import json
import platform
import warnings
import importlib.metadata as metadata
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr, ks_2samp, chi2_contingency
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, average_precision_score, brier_score_loss, confusion_matrix)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nannyml as nml
nml.disable_usage_logging()

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['time_since_login_min', 'transaction_amount', 'transaction_type',
            'is_first_transaction', 'user_tenure_months']
COMMON = dict(timestamp_column_name='timestamp', y_true='is_fraud',
    y_pred='predicted_fraud', y_pred_proba='predicted_fraud_proba',
    problem_type='classification_binary', chunk_period='M', metrics=['accuracy'])

def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding='utf-8')

def flatten(result):
    df = result.to_df().copy()
    df.columns = ['__'.join(map(str, c)) if isinstance(c, tuple) else c for c in df.columns]
    return df

def load_data():
    data, audit = {}, {}
    for name in ['reference', 'analysis']:
        path = ROOT/'data'/f'{name}.csv'
        df = pd.read_csv(path, parse_dates=['timestamp'])
        required = FEATURES + ['timestamp','is_fraud','predicted_fraud','predicted_fraud_proba']
        assert set(df) == set(required), f'Esquema inesperado: {name}'
        assert df.timestamp.notna().all(), 'Fechas nulas'
        for col in ['is_fraud', 'predicted_fraud']:
            assert df[col].notna().all() and set(df[col].unique()) <= {0,1}
            df[col] = df[col].astype(int)
        assert df.predicted_fraud_proba.between(0,1).all()
        for col in ['time_since_login_min','transaction_amount','user_tenure_months']:
            assert np.isfinite(df[col]).all() and (df[col] >= 0).all()
        audit[name] = dict(rows=len(df), columns=len(df.columns),
            first=str(df.timestamp.min()), last=str(df.timestamp.max()),
            missing=df.isna().sum().to_dict(), duplicate_rows=int(df.duplicated().sum()),
            duplicate_timestamps=int(df.timestamp.duplicated().sum()),
            sorted=bool(df.timestamp.is_monotonic_increasing),
            fraud_rate=float(df.is_fraud.mean()), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        data[name] = df.sort_values('timestamp').reset_index(drop=True)
    assert data['reference'].timestamp.max() < data['analysis'].timestamp.min(), 'Solapamiento temporal'
    return data['reference'], data['analysis'], audit

def monthly_metrics(df, period):
    records = []
    for month, g in df.groupby(df.timestamp.dt.to_period('M'), sort=True):
        y, pred, proba = g.is_fraud, g.predicted_fraud, g.predicted_fraud_proba
        tn, fp, fn, tp = confusion_matrix(y,pred,labels=[0,1]).ravel()
        n, acc = len(g), accuracy_score(y,pred)
        z=1.959963984540054
        center=(acc+z*z/(2*n))/(1+z*z/n)
        half=z*np.sqrt(acc*(1-acc)/n+z*z/(4*n*n))/(1+z*z/n)
        bins=pd.cut(proba,np.linspace(0,1,11),include_lowest=True)
        cal=pd.DataFrame({'p':proba,'y':y,'bin':bins}).groupby('bin',observed=True).agg(p=('p','mean'),y=('y','mean'),n=('y','size'))
        records.append(dict(month=str(month),period=period,n=n,fraud_rate=y.mean(),
            accuracy=acc,accuracy_ci_low=center-half,accuracy_ci_high=center+half,
            precision=precision_score(y,pred,zero_division=0),recall=recall_score(y,pred,zero_division=0),
            specificity=tn/(tn+fp),f1=f1_score(y,pred,zero_division=0),
            roc_auc=roc_auc_score(y,proba),average_precision=average_precision_score(y,proba),
            brier=brier_score_loss(y,proba),ece=float((abs(cal.p-cal.y)*cal.n/n).sum()),
            tn=int(tn),fp=int(fp),fn=int(fn),tp=int(tp),
            amount_mean=g.transaction_amount.mean(),amount_median=g.transaction_amount.median(),
            amount_p95=g.transaction_amount.quantile(.95),
            fn_amount=g.loc[(y==1)&(pred==0),'transaction_amount'].sum(),
            missing_type_rate=g.transaction_type.isna().mean(),
            login_under_1_rate=(g.time_since_login_min<1).mean(),
            score_05_disagreements=int(((proba>=.5).astype(int)!=pred).sum())))
    return pd.DataFrame(records)

def run_monitoring(reference, analysis, out, improved=False):
    out.mkdir(parents=True,exist_ok=True)
    np.random.seed(42)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        estimator=nml.CBPE(**COMMON).fit(reference)
        # No usar las etiquetas de produccion para estimar el rendimiento.
        estimated=estimator.estimate(analysis.drop(columns='is_fraud'))
        calculator=nml.PerformanceCalculator(**COMMON).fit(reference)
        realized=calculator.calculate(analysis)
        drift_ref, drift_ana = reference.copy(),analysis.copy()
        if improved:
            for df in [drift_ref,drift_ana]:
                df['transaction_type']=df.transaction_type.fillna('__MISSING__')
        drift=nml.UnivariateDriftCalculator(column_names=FEATURES,
            timestamp_column_name='timestamp', chunk_period='M',
            continuous_methods=['kolmogorov_smirnov'], categorical_methods=['chi2'],
            treat_as_categorical=['transaction_type','is_first_transaction']).fit(drift_ref).calculate(drift_ana)
        avg=nml.SummaryStatsAvgCalculator(column_names=['transaction_amount'],
            timestamp_column_name='timestamp',chunk_period='M').fit(reference).calculate(analysis)
        ranker=nml.CorrelationRanker().fit(realized.filter(period='reference'))
        ranking_all=ranker.rank(drift,realized,only_drifting=True)
        ranking_analysis=ranker.rank(drift.filter(period='analysis'),realized.filter(period='analysis'),only_drifting=True)
    for name,result in [('estimated',estimated),('realized',realized),('drift',drift),('average',avg)]:
        flatten(result).to_csv(out/f'{name}.csv',index=False)
    ranking_all.to_csv(out/'ranking_all.csv',index=False)
    ranking_analysis.to_csv(out/'ranking_analysis.csv',index=False)
    e,r=estimated.filter(period='analysis').to_df(),realized.filter(period='analysis').to_df()
    assert e[('chunk','key')].tolist()==r[('chunk','key')].tolist(), 'Meses no alineados'
    perf=pd.DataFrame({'month':e[('chunk','key')].values,
        'estimated_accuracy':e[('accuracy','value')].values,
        'realized_accuracy':r[('accuracy','value')].values,
        'estimated_alert':e[('accuracy','alert')].values,
        'realized_alert':r[('accuracy','alert')].values,
        'estimated_lower':e[('accuracy','lower_threshold')].values,
        'estimated_upper':e[('accuracy','upper_threshold')].values,
        'realized_lower':r[('accuracy','lower_threshold')].values,
        'realized_upper':r[('accuracy','upper_threshold')].values})
    perf['joint_alert']=perf.estimated_alert & perf.realized_alert
    perf['absolute_estimation_error']=abs(perf.estimated_accuracy-perf.realized_accuracy)
    perf.to_csv(out/'performance_comparison.csv',index=False)
    monthly=monthly_metrics(analysis,'analysis')
    np.testing.assert_allclose(perf.realized_accuracy,monthly.accuracy,rtol=0,atol=1e-12)
    a=avg.filter(period='analysis').to_df()
    np.testing.assert_allclose(a[('transaction_amount','value')],monthly.amount_mean,rtol=1e-12)
    alerted=a.loc[a[('transaction_amount','alert')]]
    amounts=[dict(month=str(row[('chunk','key')]),mean=float(row[('transaction_amount','value')]),
        lower_threshold=float(row[('transaction_amount','lower_threshold')]),
        upper_threshold=float(row[('transaction_amount','upper_threshold')])) for _,row in alerted.iterrows()]
    chosen=ranking_analysis if improved else ranking_all
    months=[f'{calendar.month_name[pd.Period(m).month].lower()}_{pd.Period(m).year}' for m in perf.loc[perf.joint_alert,'month']]
    answer=dict(months_with_performance_alerts=months,
        highest_correlation_feature=None if chosen.empty else chosen.iloc[0].column_name,
        alert_avg_transaction_amount=round(amounts[0]['mean'],4) if len(amounts)==1 else None,
        amount_alerts=amounts,needs_calibration=bool(estimator.needs_calibration),
        estimation_mae=float(perf.absolute_estimation_error.mean()),
        ranking_scope='analysis' if improved else 'reference_and_analysis',
        checks=['exactitud coincide con sklearn (1e-12)','importe medio coincide con pandas (1e-12)',
                'estimacion sin etiquetas de produccion','meses alineados'])
    save_json(out/'answers.json',answer)
    save_json(out/'warnings.json',sorted(set(str(w.message) for w in caught)))
    return answer,perf,drift,realized

def bh_adjust(p):
    p=np.asarray(p,float); idx=np.argsort(p); adj=np.minimum.accumulate((p[idx]*len(p)/np.arange(1,len(p)+1))[::-1])[::-1]
    out=np.empty(len(p)); out[idx]=np.minimum(adj,1); return out

def robustness(reference,analysis,drift,realized,out):
    d=drift.filter(period='analysis').to_df(); r=realized.filter(period='analysis').to_df()
    base=realized.filter(period='reference').to_df()[('accuracy','value')].mean()
    change=abs(r[('accuracy','value')].to_numpy()-base)
    ranks=[]
    for feature in FEATURES:
        method='chi2' if feature in ['transaction_type','is_first_transaction'] else 'kolmogorov_smirnov'
        values=d[(feature,method,'value')].to_numpy()
        pc=pearsonr(values,change); sc=spearmanr(values,change)
        loo=[pearsonr(np.delete(values,i),np.delete(change,i)).statistic for i in range(len(change))]
        ranks.append(dict(feature=feature,pearson_r=pc.statistic,pearson_p=pc.pvalue,
            spearman_r=sc.statistic,spearman_p=sc.pvalue,loo_min=min(loo),loo_max=max(loo),months=len(change)))
    rank=pd.DataFrame(ranks);rank['pearson_p_bh']=bh_adjust(rank.pearson_p)
    rank.sort_values('pearson_r',ascending=False).to_csv(out/'correlation_robustness.csv',index=False)
    tests=[]
    for month,g in analysis.groupby(analysis.timestamp.dt.to_period('M'),sort=True):
        for f in FEATURES:
            if f in ['transaction_type','is_first_transaction']:
                x=reference[f].fillna('__MISSING__').astype(str).value_counts()
                y=g[f].fillna('__MISSING__').astype(str).value_counts()
                counts=pd.concat([x,y],axis=1).fillna(0).T.to_numpy()
                stat,p,_,_=chi2_contingency(counts,correction=False)
            else:
                stat,p=ks_2samp(reference[f],g[f])
            tests.append(dict(month=str(month),feature=f,statistic=stat,p_value=p))
    tests=pd.DataFrame(tests);tests['p_bh_40_tests']=bh_adjust(tests.p_value)
    tests['significant_bh_005']=tests.p_bh_40_tests<.05
    tests.to_csv(out/'drift_multiple_tests.csv',index=False)

def make_figures(monthly,perf,out):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(3,1,figsize=(11,10),constrained_layout=True)
    x=np.arange(len(monthly)); prod=monthly.period.eq('analysis').to_numpy(); xp=x[prod]
    axes[0].plot(x,100*monthly.accuracy,'o-',label='Exactitud observada',color='#155e75')
    axes[0].fill_between(x,100*monthly.accuracy_ci_low,100*monthly.accuracy_ci_high,color='#155e75',alpha=.13,label='IC Wilson 95%')
    axes[0].plot(xp,100*perf.estimated_accuracy,'s--',label='Exactitud estimada (CBPE)',color='#c77700')
    axes[0].axhline(100*perf.realized_lower.iloc[0],ls=':',color='#ba324f',label='Umbral inferior observado')
    axes[0].set(ylabel='Exactitud (%)',title='El deterioro se detecta comparando estimacion y resultado real')
    axes[1].plot(x,100*monthly.recall,'o-',label='Recall de fraude',color='#ba324f')
    axes[1].plot(x,100*monthly.precision,'s-',label='Precision de fraude',color='#155e75')
    axes[1].set(ylabel='Porcentaje (%)',title='Cuantos fraudes se detectan y cuantas alertas son correctas')
    axes[2].plot(x,monthly.amount_mean,'o-',color='#155e75',label='Media mensual')
    axes[2].plot(x,monthly.amount_median,'s--',color='#c77700',label='Mediana mensual')
    axes[2].set(ylabel='Importe (GBP)',title='La media y la mediana describen aspectos distintos de los importes')
    for ax in axes:
        ax.axvline(xp[0]-.5,color='#777',ls='--',lw=1)
        ax.set_xticks(x,monthly.month,rotation=60,ha='right');ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8,ncol=2)
    fig.savefig(out/'monitoring.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    axes[0].bar(x,100*monthly.login_under_1_rate,color=['#94a3b8' if not v else '#155e75' for v in prod])
    axes[0].set(title='Transacciones antes de 1 minuto del login',ylabel='Porcentaje del mes (%)')
    axes[1].bar(x,monthly.fn,color=['#94a3b8' if not v else '#ba324f' for v in prod])
    axes[1].set(title='Fraudes no detectados por mes',ylabel='Transacciones (FN)')
    for ax in axes:
        ax.set_xticks(x,monthly.month,rotation=70,ha='right');ax.grid(axis='y',alpha=.2)
    fig.savefig(out/'diagnosis.png',dpi=170);plt.close(fig)

def additional_evidence(reference,analysis,out):
    ref,ana=reference.copy(),analysis.copy()
    ref['phase']='referencia'
    ana['phase']=np.where(ana.timestamp<'2019-04-01','produccion_estable','produccion_alerta')
    df=pd.concat([ref,ana],ignore_index=True)
    df['error']=df.is_fraud!=df.predicted_fraud
    df['early']=df.time_since_login_min<1
    df['fn']=(df.is_fraud==1)&(df.predicted_fraud==0)
    df['fp']=(df.is_fraud==0)&(df.predicted_fraud==1)
    df.groupby('phase').agg(n=('is_fraud','size'),fraud_rate=('is_fraud','mean'),
        error_rate=('error','mean'),fn=('fn','sum'),fp=('fp','sum'),early_count=('early','sum'),
        early_rate=('early','mean'),amount_mean=('transaction_amount','mean')).to_csv(out/'phase_summary.csv')
    df.groupby(['phase','is_fraud']).agg(n=('is_fraud','size'),amount_mean=('transaction_amount','mean'),
        early_rate=('early','mean'),login_mean=('time_since_login_min','mean')).to_csv(out/'segments.csv')
    threshold_check={str(t):int(((df.predicted_fraud_proba>=t).astype(int)!=df.predicted_fraud).sum())
                     for t in [.5,.6,.65,.66,.7]}
    save_json(out/'prediction_threshold_check.json',dict(disagreements=threshold_check,
        note='0.65 reproduce las etiquetas suministradas. No se optimizo ni cambio el modelo.'))

def run(stage='all'):
    reference,analysis,audit=load_data()
    output=ROOT/'output';output.mkdir(exist_ok=True)
    save_json(output/'data_audit.json',audit)
    monthly=pd.concat([monthly_metrics(reference,'reference'),monthly_metrics(analysis,'analysis')],ignore_index=True)
    monthly.to_csv(output/'monthly_metrics.csv',index=False)
    if stage in ['baseline','all']:
        answer,*_=run_monitoring(reference,analysis,output/'v1',False)
        print('PRIMERA PRUEBA',json.dumps(answer,ensure_ascii=False))
    if stage in ['final','all']:
        answer,perf,drift,realized=run_monitoring(reference,analysis,output/'final',True)
        robustness(reference,analysis,drift,realized,output/'final')
        additional_evidence(reference,analysis,output/'final')
        make_figures(monthly,perf,output/'final')
        if (output/'v1'/'performance_comparison.csv').exists():
            v1=pd.read_csv(output/'v1'/'performance_comparison.csv')
            np.testing.assert_allclose(v1.estimated_accuracy,perf.estimated_accuracy,atol=1e-12,rtol=0)
            assert v1.joint_alert.tolist()==perf.joint_alert.tolist()
        print('RESULTADO FINAL',json.dumps(answer,ensure_ascii=False))
    versions={'python':platform.python_version()}
    for p in ['nannyml','pandas','numpy','scipy','scikit-learn','matplotlib','statsmodels','category-encoders']:
        versions[p]=metadata.version(p)
    save_json(output/'versions.json',versions)
    return locals()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['baseline','final','all'],default='all')
    run(parser.parse_args().stage)
