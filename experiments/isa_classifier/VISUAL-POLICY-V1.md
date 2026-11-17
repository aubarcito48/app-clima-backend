# Primera corrección visual: etiquetas y empalme inglés

La revisión de apertura/cierre mejora los indicadores visuales con **el mismo
Random Forest y el mismo PCM**. El candidato de empalme mejora modestamente la
unión de imágenes, pero aporta menos al cierre durante habla que las etiquetas
solas. Por eso el visor abre con **Sólo etiquetas revisadas** y expone el empalme
como opción. No se promueve ninguna política a producción.

Protocolo fijado antes de medir: [PROTOCOL-VISUAL-POLICY.md](PROTOCOL-VISUAL-POLICY.md).
Antecedente: [relevamiento con skills](SKILLS-AUDIT.md). Se aplicaron la revisión
de timing/poses de Animator's Survival Kit y las mediciones faciales de Image Eye
Checker; voz y sus marcas se mantienen como fueron auditadas con Audio Lens y
Prosody Lens. No se hace una nueva síntesis ni entrenamiento.

## Referencias visuales

Se inspeccionaron tres láminas de 68 bocas por idioma, extraídas de los mismos
atlas publicados. El registro enlaza índices del atlas, frame original y SHA256.
Se asigna apertura/cierre a **374/408 frames**; 34 quedan inciertos. Son etiquetas
de inspección visual del agente, **no anotaciones humanas certificadas**.

ES: 152 abiertos, 42 cerrados, 10 inciertos. EN: 124 abiertos, 56 cerrados,
24 inciertos. No se elimina ni modifica ninguna imagen; se preservan parpadeos,
ojos, cuerpo y expresiones completos.

Contra las etiquetas propagadas anteriores se corrigen 22 contradicciones binarias:

- ES abiertos antes tratados como X: #43–46, #51, #79, #85–86.
- ES cerrados antes tratados como habla: #11, #62–63, #137–138, #188–190.
- EN abierto antes tratado como X: #43.
- EN cerrados antes tratados como habla: #66–69 y #111.

Cuando una boca está abierta pero no se puede justificar un visema fino nuevo,
se conserva esa incertidumbre: `?` significa apertura confirmada, forma fina
sin confirmar. No se inventa un fonema. Si la etiqueta anterior fina no contradice
la apertura, permanece provisional. Los puckers y transiciones dudosos no se
reclasifican como silencio a partir del valor de mandíbula.

Los catálogos sin `mouthStates` conservan el comportamiento anterior. En el
catálogo revisado, el coste distingue apertura genérica de cierre confirmado.
No se amplía la deriva, el máximo salto ni los límites de pose/movimiento.
ES conserva la aceleración extra desactivada y su rango publicado.

## Comparación pareada

32 audios finales anteriores, 16 por idioma: ocho consejos en dos velocidades.
Son datos ya vistos, utilizados aquí para diagnosticar el selector, **no un nuevo
test independiente del aprendizaje**. Se puntúan tres recorridos con el mismo RF:
anterior, sólo etiquetas, etiquetas más empalme candidato. Total: 96 planes.

La referencia común de apertura/cierre es la revisión visual. Se usa la
intersección de instantes con estados conocidos en los tres recorridos; los
inciertos no se cuentan como aciertos. Cobertura del consejo: 91,0 % ES y 80,3 % EN.

### Cierres cuando RF pide apertura y hay evidencia de habla

Sólo consejo, fuera de pausas insertadas. Mismo denominador pareado por idioma.

| Idioma | Anterior | Sólo etiquetas | Etiquetas + empalme |
| --- | ---: | ---: | ---: |
| ES, 2.055 instantes | 239 / 11,63 % | 185 / 9,00 % | 185 / 9,00 % |
| EN, 1.297 instantes | 117 / 9,02 % | 64 / 4,93 % | 77 / 5,94 % |

Con sólo etiquetas EN hay 53 cierres incompatibles menos, aproximadamente 45 %
de reducción de este indicador. No implica 95 % de precisión ni de calidad visual.

### Boca cerrada durante pausas PCM verificadas

| Idioma | Instantes pareados | Anterior | Sólo etiquetas | Etiquetas + empalme |
| --- | ---: | ---: | ---: | ---: |
| ES | 125 de 131 | 5 / 4,00 % | 19 / 15,20 % | 19 / 15,20 % |
| EN | 116 de 127 | 59 / 50,86 % | 85 / 73,28 % | 85 / 73,28 % |

El valor español sigue siendo bajo: el recorrido no puede llegar siempre a un
cierre en la pausa sin romper sus restricciones. Es una razón concreta para
trabajar luego con continuaciones de secuencias cortas, no para declarar el caso
resuelto. Las cifras anteriores del relevamiento usaban etiquetas visuales débiles
distintas: no deben compararse directamente con estas cifras revisadas.

## Empalme candidato EN

La selección usa sólo imágenes, sin elegir según los audios. Conserva una
secuencia hacia adelante de al menos seis segundos, no corta durante un
parpadeo y exige apertura compatible. Se revisan las mejores opciones en una
lámina de salida/entrada de seis frames por opción.

- Antes: índices 12–179, ciclo de 7,000 s.
- Candidato: índices 10–184, ciclo de 7,292 s.
- Diferencia facial en unión: 0,05737 → 0,05180, reducción de **9,7 %**.
- Discontinuidad fotométrica de velocidad: 0,02084 → 0,01141, reducción de **45,3 %**.

Son medidas de píxeles en una región facial excluyendo la boca, no distancias
anatómicas ni una garantía de naturalidad. La mejora de pose es pequeña y el
empalme sigue mereciendo revisión perceptual. En el banco, las expresiones de
inicio/fin no son idénticas. No se disimula con fundidos largos ni reversa.

El planificador rechaza un `reviewedLoop` no verificado o aplicado a otro rango.
Además de los saltos de dos o más frames, la auditoría comprueba el retorno
normal del último al primero de este ciclo. Cada retrato del visor usa su propio
rango real en el renderer: no es solamente una diferencia dibujada en las barras.

## Prueba que puede abrir el usuario

`tmp/isa-own-classifier/visual-policy-review-v1/index.html`:

- Izquierda: recorrido anterior; derecha: política elegida en **Versión nueva**.
- Predeterminado: **Sólo etiquetas revisadas**.
- Alternativa: **Etiquetas + empalme inglés candidato**; ES conserva su ciclo.
- Un audio, un reloj, mismos fonemas/RF y barras alineadas. La voz mantiene su
  velocidad automática anterior. El reproductor permanece en 1×.
- El control de aceleración conserva el perfil independiente por idioma.

Se conservaron la lluvia de referencia y dos consejos finales nuevos por idioma.
El audio de ambos lados y sus marcas RF se comparan por igualdad antes de probar.
No se afirma que la concordancia del modelo haya aumentado: no se entrenó.

## Verificación

- Los 32 controles reproducen exactamente los caminos congelados del relevamiento
  previo, antes de aplicar cambios. Se conservan los experimentos anteriores.
- Los 96 planes cumplen deriva, saltos hacia adelante y límites de pose/movimiento;
  sus relojes son monótonos a 120 Hz y no acumulan retrasos al buscar un instante.
- Pruebas nuevas: referencia anterior intacta, override de cierre, apertura con
  forma fina incierta, rechazo de estados inválidos y de empalmes/rangos inválidos.
- Pasa la prueba existente del planificador y los 84 tests Python experimentales.
- Playwright comprueba ambos idiomas y modos, reproducción, seeking antes/después
  del empalme, igualdad de audio/marcas RF, rango del renderer y frame real dibujado,
  barras, cambio de aceleración y móvil. Sin errores de consola ni peticiones HTTP.
- Se inspeccionan las láminas y capturas del visor. Falta la evaluación perceptual
  del usuario sobre las secuencias completas; no se reemplaza por estos tests.

No se modifica el frontend publicado, el backend de producción, modelos, WAV ni
atlas originales. El parche del rango del renderer existe sólo en la compilación
del HTML experimental; el archivo fuente `isa-portrait.ts` queda intacto.

## Artefactos y reproducción

Bajo `tmp/isa-own-classifier/visual-policy-v1/`: `policy.json`, catálogos ES/EN,
`review-es.json`, `review-en.json`, seis láminas de bocas y `seam-candidates-en.png`.
En `visual-policy-review-v1/`: visor, comparación, `evaluation.json`,
`viewer-check.json` y capturas por idioma/modo. `boosted/previous` en el batch de
entrada son TDNN/RF; esta ronda utiliza exclusivamente las marcas `previous` RF.

```powershell
python experiments/isa_classifier/prepare_visual_policy.py --audit tmp/isa-own-classifier/skills-audit-v1 --frontend ../app-clima --output tmp/isa-own-classifier/visual-policy-reproduction
python experiments/isa_classifier/prepare_visual_demo.py --source tmp/isa-own-classifier/neural-direct-v1 --policy tmp/isa-own-classifier/visual-policy-reproduction --frontend ../app-clima --output tmp/isa-own-classifier/visual-review-reproduction
node experiments/isa_classifier/build_auto_rate_demo.mjs ../app-clima tmp/isa-own-classifier/visual-review-reproduction
```

Siguiente paso: comparar continuaciones cortas compatibles con estas referencias
revisadas y el mismo RF, evaluando disponibilidad de cierre y continuidad a la vez.
Esta etapa no incorpora todavía un selector de secuencias con ramificaciones.
