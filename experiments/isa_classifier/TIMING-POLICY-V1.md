# Calibración automática de reproducción · 16/11/2026

Se probó aprender los parámetros de reproducción local de la animación sobre el
híbrido entrenado. Es una búsqueda acotada de política temporal, no una red nueva
que descubra fonemas o corrija por sí sola etiquetas ambiguas.

## Método

Predicciones congeladas del híbrido, energía PCM, pausas realmente insertadas y
catálogos visuales actuales. Los audios y modelos permanecen intactos.

Sólo inglés: 40 frases train, 8 dev y 16 test. Son los splits de la ronda híbrida,
no nuevas frases externas. Español conserva exactamente su perfil anterior.

Seis alternativas prefijadas: separación entre ajustes de 83/125 ms y límite de
desplazamiento de 4/6/8 frames. Sin desfase global ni cambio de velocidad de voz.
La política actúa por fragmento mediante el planificador, que conserva avance
monótono, límites de movimiento/pose y aceleración local sólo en cierres compatibles.

Objetivo: reducir boca visual cerrada durante habla con solicitud abierta, con
penalización por perder pausas conocidas, cierres A necesarios y correspondencia
visual general. La referencia acústica Rhubarb y las etiquetas de imágenes son
débiles; estos indicadores no son calidad percibida ni fronteras humanas fiables.

Train propone hasta tres candidatos, además del perfil actual. Dev selecciona
sin aumentar sus indicadores de pérdida de pausas/cierres necesarios. Después
se congela `policy.json` y se accede a resultados test una sola vez.

## Resultado

Dev eligió el perfil actual: 83 ms, desplazamiento máximo 6 frames y aceleración
local activada. Por lo tanto **esta calibración no añade mejora** frente al
planificador ya existente. No se cambiaron valores para presentar una ganancia.

En los 16 test, tanto antes como después se detectan 69/1119 instantes de boca
cerrada cuando la referencia pide apertura y hay evidencia energética de habla.
Las pérdidas visuales en pausas y cierres A también permanecen iguales.

Un límite importante: el selector no encuentra/elige suficientes poses cerradas
en las posiciones requeridas, bajo su recorrido y restricciones de continuidad.
Esto no demuestra que falten imágenes; las etiquetas son provisionales y puede
ser un problema de orden/selección. Ampliar el banco indiscriminadamente o seguir
calibrando los mismos parámetros no resuelve necesariamente esa limitación.

La demo inglesa a 3,151 s cae en una región de baja energía candidata de
3,078–3,552 s, sin pausa insertada en ese instante. No es silencio confirmado.
El detector conservador no debe adelantarla sólo porque una captura muestre
la boca cerrada: una consonante suave también puede tener poca energía.

## Artefactos y reproducción

`tmp/isa-own-classifier/timing-policy-v1/`: `batch.json`, `policy.json` y
`evaluation.json`, con métricas y resultados por caso.

```powershell
python experiments/isa_classifier/prepare_timing_policy.py --corpus tmp/isa-own-classifier/corpus-phonetic-v1/corpus.json --models tmp/isa-own-classifier/hybrid-phonetic-v1 --output tmp/isa-own-classifier/timing-policy-nuevo
node experiments/isa_classifier/train_timing_policy.mjs ../app-clima tmp/isa-own-classifier/timing-policy-nuevo
```

Se comprobaron todos los saltos de los planes evaluados: avance positivo/cero,
desplazamiento acotado y uniones permitidas por pose/movimiento. Los hashes de
train/dev son disjuntos de los test. El perfil español y producción no cambian.

No se exige revisión manual en cada reproducción: las correcciones del
planificador ya son automáticas. La revisión humana propuesta es para construir
un pequeño conjunto de evaluación fiable, no para operar la aplicación.
