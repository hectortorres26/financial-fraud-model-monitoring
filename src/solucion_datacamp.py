"""Solucion para ejecutar en una celda de DataCamp; respuestas calculadas, no prefijadas."""
from pathlib import Path
import calendar
import numpy as np
import pandas as pd
import nannyml as nml
nml.disable_usage_logging()
np.random.seed(42)
data_dir=Path('.') if Path('reference.csv').exists() else Path('data')
reference=pd.read_csv(data_dir/'reference.csv',parse_dates=['timestamp'])
analysis=pd.read_csv(data_dir/'analysis.csv',parse_dates=['timestamp'])
parameters=dict(timestamp_column_name='timestamp',y_true='is_fraud',
    y_pred='predicted_fraud',y_pred_proba='predicted_fraud_proba',
    problem_type='classification_binary',metrics=['accuracy'],chunk_period='M')
cbpe=nml.CBPE(**parameters).fit(reference)
estimated=cbpe.estimate(analysis.drop(columns='is_fraud'))
realized=nml.PerformanceCalculator(**parameters).fit(reference).calculate(analysis)
e=estimated.filter(period='analysis').to_df()
r=realized.filter(period='analysis').to_df()
assert e[('chunk','key')].tolist()==r[('chunk','key')].tolist()
joint=e[('accuracy','alert')].to_numpy() & r[('accuracy','alert')].to_numpy()
months_with_performance_alerts=[
    f'{calendar.month_name[pd.Period(key).month].lower()}_{pd.Period(key).year}'
    for key in e.loc[joint,('chunk','key')]]
features=['time_since_login_min','transaction_amount','transaction_type',
          'is_first_transaction','user_tenure_months']
drift_reference=reference.copy()
drift_analysis=analysis.copy()
for frame in [drift_reference,drift_analysis]:
    frame['transaction_type']=frame.transaction_type.fillna('__MISSING__')
drift=nml.UnivariateDriftCalculator(column_names=features,
    timestamp_column_name='timestamp',chunk_period='M',
    continuous_methods=['kolmogorov_smirnov'],categorical_methods=['chi2'],
    treat_as_categorical=['transaction_type','is_first_transaction']
    ).fit(drift_reference).calculate(drift_analysis)
ranker=nml.CorrelationRanker().fit(realized.filter(period='reference'))
ranking=ranker.rank(drift.filter(period='analysis'),realized.filter(period='analysis'),only_drifting=True)
highest_correlation_feature=str(ranking.iloc[0].column_name)
average=nml.SummaryStatsAvgCalculator(column_names=['transaction_amount'],
    timestamp_column_name='timestamp',chunk_period='M').fit(reference).calculate(analysis)
a=average.filter(period='analysis').to_df()
alerted_amounts=a.loc[a[('transaction_amount','alert')],('transaction_amount','value')]
assert len(alerted_amounts)==1, 'Revisar los meses con alerta antes de asignar un unico importe'
alert_avg_transaction_amount=round(float(alerted_amounts.iloc[0]),4)
print('months_with_performance_alerts =',months_with_performance_alerts)
print('highest_correlation_feature =',highest_correlation_feature)
print('alert_avg_transaction_amount =',alert_avg_transaction_amount)
