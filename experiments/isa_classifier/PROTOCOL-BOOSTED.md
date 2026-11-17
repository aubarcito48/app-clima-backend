# Aprendizaje por árboles y decodificación temporal

Usar los mismos 139 train / 32 dev de la ronda ampliada, sin mover test a train.
Añadir 16 consejos exclusivamente test (8 ES, 8 EN), con versiones actual/auto
cuando se compruebe una reducción real. Conservar grupos de frase entre splits.

Entradas idénticas a identidad fonética: audio, ritmo, duraciones y vocabulario
aprendido sólo de train, con contexto (-4,-2,0,2,4). Nuevo aprendiz: XGBoost CPU,
hist, max_bin 64, 160 rondas, eta .08, max_depth 3/5, balance .25/.5, cap 4,
reg_lambda 10, min_child_weight 10, subsample .85 y colsample_bytree .8. Dos hilos.
Semilla fija 20261116. Cuatro ajustes de árboles por idioma, sin early stopping
ni elección del número de rondas mirando test.

Calibración dev: penalización logarítmica de cierre A/X 0/.25 y transiciones
0/.05. Total 16 combinaciones/idioma. Entre candidatos que no aumenten el cierre
incorrecto del consejo dev más de .002, conserven cierre en pausas a menos de
.01 y recall A a menos de .03 del modelo de identidad anterior, elegir F1 macro
dev agrupado por frase y concordancia como desempate. Si ninguno cumple, guardar
el mejor F1 sólo como diagnóstico y no presentarlo como sustituto seguro.

Peso del consejo 1, saludo/despedida .25, dividido por variantes de frase. Las
etiquetas son Rhubarb débil y la métrica primaria excluye frases repetidas.
Congelar antes de evaluar el test nuevo contra identidad anterior y V7 sobre el
mismo PCM. No buscar 100 % ajustando sobre test. La animación sigue siendo una
evaluación separada con banco y automatizaciones conservados, fuera de producción.

Dependencia instalada exclusivamente en el entorno experimental. Exportar pesos
en UBJSON generado por XGBoost, sin pickle. No se incorpora al runtime de Render.
