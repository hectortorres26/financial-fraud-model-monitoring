# Datos del proyecto

Los archivos originales proceden de [Monitoring a Financial Fraud Detection Model, DataCamp](https://app.datacamp.com/learn/projects/2104). Se mantienen fuera del repositorio público. Para reproducir el análisis, accede al proyecto con tu propia cuenta y descarga `reference.csv` y `analysis.csv` desde su espacio de trabajo. Copia ambos archivos aquí sin cambiar los nombres.

| Archivo | Filas | Periodo | Uso |
|---|---:|---|---|
| `reference.csv` | 50 207 | Enero–octubre de 2018 | Ajustar los monitores y sus umbrales |
| `analysis.csv` | 39 967 | Noviembre de 2018–junio de 2019 | Evaluar el comportamiento posterior |

## Diccionario de datos

| Columna | Significado | Función |
|---|---|---|
| `timestamp` | Fecha y hora | Agrupación mensual |
| `time_since_login_min` | Minutos desde el inicio de sesión | Variable de entrada continua |
| `transaction_amount` | Importe en GBP | Variable de entrada continua |
| `transaction_type` | Tipo de transacción | Variable categórica; contiene nulos |
| `is_first_transaction` | Indicador de primera transacción | Variable categórica binaria |
| `user_tenure_months` | Antigüedad del usuario en meses | Variable de entrada continua |
| `is_fraud` | Etiqueta observada: 1 = fraude | Evaluación del rendimiento real |
| `predicted_fraud` | Clase predicha por el modelo | Predicción suministrada |
| `predicted_fraud_proba` | Probabilidad estimada de fraude | Entrada a CBPE |

Cada archivo contiene nueve columnas. La auditoría comprueba el esquema, dominios, duplicados y separación temporal. Las huellas SHA-256 están en `output/data_audit.json`. No se eliminan transacciones; los nulos de `transaction_type` se representan como `__MISSING__` en el diagnóstico final.
