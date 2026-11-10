# Metodología y decisiones analíticas

## Separación temporal

La referencia cubre enero–octubre de 2018; producción cubre noviembre de 2018–junio de 2019. Los monitores se ajustan sobre referencia y se aplican a producción en bloques mensuales (`chunk_period='M'`). Se mantienen las clases predichas suministradas; el umbral 0,65 reproduce esas clases, mientras que 0,50 cambiaría el problema.

## Exactitud estimada y observada

CBPE utiliza probabilidades calibradas para estimar métricas sin etiquetas de producción. La etiqueta `is_fraud` se elimina explícitamente al llamar a `estimate`. `PerformanceCalculator` utiliza esas etiquetas para contrastar la estimación. Las alertas se combinan con AND después de verificar que los meses están alineados. Los límites de alerta y los intervalos Wilson de las figuras cumplen funciones distintas.

## Deriva y ranking

Se usa Kolmogorov–Smirnov para variables continuas y chi-cuadrado para categóricas. `is_first_transaction` se trata como categórica. Los nulos de `transaction_type` se conservan como categoría explícita en la versión final. `CorrelationRanker` se ajusta con el rendimiento de referencia y relaciona la deriva con el cambio absoluto respecto a su media. El ranking final utiliza solo los ocho meses de producción y solo variables con deriva.

La correlación principal para `time_since_login_min` es 0,97037. Una primera prueba sobre los 18 meses mezclaba referencia y producción; la revisión separa el ámbito de diagnóstico. Se calculan Spearman, sensibilidad al excluir cada mes y ajustes Benjamini–Hochberg. Estos contrastes son exploratorios: ocho bloques temporales no proporcionan evidencia causal.

## Importe medio y verificación

`SummaryStatsAvgCalculator` ajusta límites de la media con referencia. Junio presenta una media de 3069,818355 GBP, superior al límite de 3021,411123 GBP. El resultado solicitado se redondea a cuatro decimales. Se exige un único mes alertado antes de asignar el escalar. Se contrastan medias con pandas y exactitud con scikit-learn.

## Primera prueba y solución revisada

El pipeline genera `output/v1` para la primera prueba y `output/final` para la revisión. La primera carpeta se mantiene local; el notebook conserva sus resultados. Las mejoras de tratamiento de nulos y selección del periodo del ranking mantienen las tres respuestas solicitadas y las estimaciones CBPE.

## Evidencia y límites

La aprobación del corrector se documenta en `evidence/datacamp_aprobado.jpg`. Se obtuvo con la misma solución en Microsoft Edge después de fallos de envío en el navegador integrado; no se identificó una causa técnica definitiva de esos fallos. La aprobación no constituye validación de un sistema bancario real.

El cambio del login afecta tanto a fraude como a operaciones legítimas. Se debe investigar la instrumentación, los procesos y la población antes de atribuirlo a acciones de estafadores. Las recomendaciones de reentrenamiento o cambio de umbral requieren datos futuros, un modelo disponible y costes de error; no se ejecutan en este proyecto.

## Referencias

- [Enunciado y datos: DataCamp 2104](https://app.datacamp.com/learn/projects/2104)
- [NannyML: estimación del rendimiento](https://nannyml.readthedocs.io/en/stable/how_it_works/performance_estimation.html)
- [NannyML: implementación de CorrelationRanker](https://nannyml.readthedocs.io/en/stable/_modules/nannyml/drift/ranker.html)

Las versiones reproducibles están fijadas en `requirements.txt`; la documentación web puede corresponder a versiones posteriores.
