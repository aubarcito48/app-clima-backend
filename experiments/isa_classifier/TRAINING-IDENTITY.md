# Identidad fonética y tiempos · 16/11/2026

Se completó otra ronda, manteniendo voz automática, aceleración local de frames,
pausas y banco de imágenes. El nuevo clasificador conserva las 48 entradas
anteriores y añade identidad one-hot del fonema/etiqueta activa de Piper.

## Entrenamiento y datos

- Mismos 139 audios train y 32 dev de la ronda ampliada; no se trasladaron test a
  entrenamiento. Esta ronda cambia representación, no aumenta las frases train.
- Vocabulario aprendido sólo de train por idioma: 43 entradas ES y 49 EN,
  incluyendo símbolos prosódicos, puntuación, gap y unknown. No son 43/49 fonemas
  lingüísticos distintos. Entradas totales: 91 ES y 97 EN, con contexto temporal.
- Vocabularios congelados y almacenados con el modelo. Un símbolo nuevo usa la
  categoría unknown; una matriz de columnas con otro orden se rechaza.
- 16 candidatos prefijados por idioma, seleccionados en dev por F1 macro del
  consejo agrupado por frase. Ambos eligieron balance .5, ridge 1, transición .05.
- Etiquetas débiles Rhubarb, no anotaciones humanas ni un reconocedor de fonemas
  nuevo: los fonemas de entrada vienen del sintetizador existente.

Se añadieron 16 consejos exclusivamente test, 8 por idioma, sin coincidencias
exactas con el corpus anterior. Con las variantes de velocidad aceptadas son
29 nuevos audios y 260 grabaciones aceptadas en total, 200 grupos de frases.
ES test: 13 grabaciones / 8 grupos; EN: 16 / 8 grupos. Las versiones históricas
test se conservaron pero no se usan en la comparación primaria de esta ronda.

## Control de calidad de la velocidad

La generación encontró `es-identity-test-01-automatic`, cuya segunda frase tenía
la misma duración que la normal, pese a solicitar factor .9651. Se preservó el
WAV y su diagnóstico, pero se excluyó esa variante del corpus. Se conservó la
versión normal. El generador ahora realiza ese rechazo automáticamente si alguna
frase seleccionada no aumenta realmente su duración.

La primera auditoría falló y una ejecución inicial de entrenamiento llegó a
emitir un diagnóstico parcial español antes de ser detenida. No se utilizaron
esas puntuaciones para modificar candidatos ni datos train/dev. Tras corregir
la admisión de la variante por sus tiempos reales, se auditó el corpus completo
y se ejecutó la ronda final en otra carpeta (`hybrid-identity-v2`). El directorio
`hybrid-identity-v1` es parcial y no es el resultado final.

La auditoría final verificó los 60 pares baseline/automático aceptados, sus
pausas, identidades PCM y separación de grupos. No se exige que un simple cambio
de parámetro equivalga a una reducción real: se comprueba el audio generado.

## Test nuevo: media entre grupos de frases

| Variante | ES concordancia | ES F1 macro | EN concordancia | EN F1 macro |
| --- | ---: | ---: | ---: | ---: |
| V7 | 57,63 % | 32,84 % | 58,11 % | 44,42 % |
| Modelo ampliado anterior | 59,76 % | 35,90 % | 59,67 % | 46,79 % |
| Identidad fonética | 58,45 % | 36,93 % | 60,71 % | 47,56 % |

Son las mismas frases y PCM para cada columna comparativa. No deben compararse
directamente con cifras de rondas que usaron otras frases. Se excluyen saludo y
despedida de la métrica primaria, y las variantes no cuentan como frases nuevas.

Frente al anterior: español pierde 1,31 puntos de concordancia y gana 1,02 F1;
inglés gana 1,05 puntos de concordancia y .77 F1. No es mejora global garantizada.

## Cierres y pausas: regresiones visibles en las métricas

Ventanas del consejo con A/X mientras la referencia pide apertura, con denominador
de todas las ventanas: ES 4,57 % -> 4,32 %; EN 4,94 % -> 5,61 % (empeora).
Cierre durante pausas insertadas: ES 81,11 % -> 83,87 %; EN 95,93 % -> 95,54 %.
El avance inglés de F1 no resuelve el problema prioritario de cierres sobre habla.
No se promovió el nuevo modelo ni se cambiaron hiperparámetros mirando test.

Ocho grupos por idioma y etiquetas débiles no justifican una afirmación de
precisión humana ni alcanzar 80/100 %. Hace falta comparar las animaciones.

## Visor completo y validación

`tmp/isa-own-classifier/identity-review-v1/index.html`: modelos anterior/nuevo,
voz actual/automática, tres muestras por idioma (incluye dos test nuevos), barras
de energía/pausas/marcas/frame elegido/control, fonema activo, búsqueda temporal
y aceleración local con el perfil de cada idioma. Cada WAV tiene sus propios
tiempos. El control de velocidad sigue siendo una regla experimental, no una
política que se entrene sola mientras el usuario reproduce.

Pasaron 66 pruebas Python, pruebas del planificador y Playwright en ES/EN para
audio exclusivo, velocidad real 1×, búsqueda, barras pintadas, cambio de modelo
sin reiniciar, aceleración, contenido nuevo, móvil y ausencia de peticiones
externas. Los botones ahora pausan el otro audio antes de pedir reproducción;
la prueba espera el estado observable del navegador para evitar una carrera.

Frontend y producción no cambiaron. El banco de imágenes y modelos anteriores
se conservan. Modelos finales y evaluación: `tmp/isa-own-classifier/hybrid-identity-v2/`.

## Reproducción

```powershell
python experiments/isa_classifier/identity_test_plan.py tmp/isa-own-classifier/identity-test-nuevo.json
.\tmp\isa-phoneme-env\Scripts\python.exe -X utf8 experiments/isa_classifier/generate_rate_expansion.py --previous tmp/isa-own-classifier/corpus-rate-balance-v1/corpus.json --plan tmp/isa-own-classifier/identity-test-nuevo.json --output tmp/isa-own-classifier/corpus-identity-nuevo
python experiments/isa_classifier/audit_rate_corpus.py tmp/isa-own-classifier/corpus-identity-nuevo/corpus.json
```

Sólo si la auditoría termina correctamente:

```powershell
python experiments/isa_classifier/train_phonetic.py --corpus tmp/isa-own-classifier/corpus-identity-nuevo/corpus.json --baseline tmp/isa-own-classifier/v7 --reference-hybrid tmp/isa-own-classifier/hybrid-rate-balanced-v1 --rate-expansion --phoneme-identity --output tmp/isa-own-classifier/identity-models-nuevo
```
