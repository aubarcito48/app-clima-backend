"""Local functionality inventory from code review and measured skill/browser results."""
import html
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from api.services.voice_chunks import speech_text

root=Path(sys.argv[1]); root.mkdir(parents=True,exist_ok=True)
normalization=[]
for language in ['es','en']:
    for value,es,en in [('90.\u00b0','90 grados','90 degrees'),('25\u00b0C','25 grados','25 degrees'),
                        ('1\u00b0','1 grado','1 degree'),('-1\u00b0','-1 grado','-1 degree'),
                        ('10km/h','10 kilómetros por hora','10 kilometers per hour')]:
        actual=speech_text(value,language);expected=es if language=='es' else en
        assert actual==expected
        normalization.append({'language':language,'source':value,'voice_text':actual,'expected':expected})
(root/'normalization.json').write_text(json.dumps(normalization,ensure_ascii=False,indent=2),encoding='utf8')
matrix=[
 ('Saludo y despedida','Verificado','Frases exactas ES/EN; saludo 160 ms y despedida sin pausa añadida. Tests de narración/servicio y corpus.'),
 ('Grados y unidades','Verificado','90.° → 90 grados/degrees; singular, negativo, °C y km/h. Diez comprobaciones textuales; no prueba auditiva de pronunciación.'),
 ('Planes del director ES/EN','Implementado','Directores separados; parámetros de speed/energy/pause validados. La selección local/Groq depende de configuración.'),
 ('Ritmo automático medido','Experimental','La doble síntesis, RF y su alineación Piper siguen en experiments. No están importados por el worker publicado.'),
 ('Energía de voz','Implementado','Piper escala las muestras por energy y limita a [-1,1]. Los 32 audios auditados no saturan; no se probaron todos los extremos posibles.'),
 ('Pausas insertadas y naturales','Parcial','Se conocen los huecos insertados. La baja energía es candidata: cambiar 250 a 60 ms multiplica las detecciones, sin validarlas.'),
 ('Rhubarb y fallback','Implementado, opcional','El código admite off/rhubarb. Sin marcas válidas conserva el reloj básico. No se inspeccionó la configuración real de Render.'),
 ('RF, XGBoost y red temporal','Experimental','Los modelos están comparados localmente. RF requiere PCM y alineación fonética de la misma síntesis; no basta con subir sus pesos.'),
 ('Clasificación visual','Experimental, revisada','374 frames con apertura/cierre revisados por el agente, 34 inciertos. Forma fina provisional; sin etiquetas humanas certificadas.'),
 ('34 bocas dudosas','Revisado, pendiente','Se extrajeron los 34 recortes del video original a 176×88. Puckers y transiciones requieren contexto; no se cambiaron etiquetas por fuerza.'),
 ('Selección de frames','Implementado + laboratorio','La app tiene selectores ES/EN. El laboratorio ofrece etiquetas nuevas y empalme candidato. Las secuencias cortas ramificadas siguen pendientes.'),
 ('Reloj de reproducción','Verificado en muestra','32 WAV con código sin modificar de la app: sin retrocesos a 120 Hz. Hay desfases locales del selector; no significa sincronía perfecta.'),
 ('Habla durante silencios','Verificado','No se congela por poner amplitud en cero. El video mantiene el frente y las marcas gobiernan su tiempo.'),
 ('Inicio y salida del habla','Verificado con hallazgo','Fundido inmediato y avance sólo hacia adelante. La lista de reposo ES aún declara cerrado #123, que la revisión ve abierto; #128 queda incierto.'),
 ('Parpadeo en reposo','Verificado','El frame observado pertenece a la pista de parpadeo. Sus ojos cerrados son una animación intencional, no imágenes defectuosas.'),
 ('Giros y expresiones','Verificado','Frente/derecha/abajo/sueño funcionan. Durante audio se prioriza el video frontal; los gestos por fragmento no sustituyen ese video a propósito.'),
 ('Movimiento reducido','Verificado','No carga nuevas páginas de habla ni anima el habla. El consejo puede seguir sonando; reposo frontal estático.'),
 ('Ocultar y volver','Verificado con simulación','Se detiene RAF al simular document.hidden y retoma el reloj. No fue una medición en un móvil ni en una pestaña real suspendida por el SO.'),
 ('Páginas lentas/fallidas','Hallazgo reproducido','Fallback conserva el retrato. Tras fallo temporal, cero reintentos en la siguiente narración del mismo idioma; reiniciar el atlas al cambiar idioma lo recupera.'),
 ('Silenciar y cambios rápidos','Verificado en tests','Detiene audio, revoca URL, cancela petición/resultado obsoleto y mantiene mute. Eso no demuestra que se aborte el proceso Piper ya ejecutándose en servidor.'),
 ('Volver a escuchar / autoplay','Oportunidad de UX','El bloqueo se informa y queda texto. Al silenciar se descarta el audio; reactivar no repite el mismo consejo por diseño. Falta reintento/replay explícito con caché.'),
 ('Voz ocupada','Implementado, recuperación pendiente','Servidor responde 429 VOZ_OCUPADA y Retry-After: 5. El servicio de voz lo trata como error genérico, sin reintento acotado del consejo vigente.'),
 ('Cancelación y limpieza','Verificado','Timers/RAF se liberan al destruir; el canvas desaparece. Los tests del servicio cubren cancelación de análisis asíncrono y audio obsoleto.'),
 ('Presencia en Sobre nosotros','Intencional','presenceOnly usa imagen y evita voz/carga del retrato animado. No es una función de habla faltante.'),
 ('Rendimiento y despliegue','Parcial','Código retiene página actual/siguiente y ejecuta una síntesis a la vez por proceso. Falta medir CPU/RSS/latencia en Render con RF y doble síntesis integrados.'),
]
portrait=json.loads((root/'portrait-functions.json').read_text()); runtime=json.loads((root/'runtime-playback.json').read_text())
report={'scope':'Isa only; source code, isolated app tests, native atlas/browser harness and prior skills evidence; no live cloud audit',
 'tests':{'backend':246,'frontend_isa':38,'browser_checks':len(portrait['checks'])},
 'matrix':[dict(feature=a,status=b,evidence=c) for a,b,c in matrix],
 'runtime_clock':runtime['summary'],'portrait_checks':portrait['checks']}
(root/'functionality.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
table=''.join(f'<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td><td>{html.escape(c)}</td></tr>' for a,b,c in matrix)
captures=''.join(f'<figure><img src="captures/{name}.png" alt="{html.escape(label)}"><figcaption>{html.escape(label)}</figcaption></figure>' for name,label in
 [('pose-isa-awake','Frente'),('pose-isa-right','Mirada a la derecha'),('pose-isa-down','Mirada abajo'),('pose-isa-sleep','Sueño'),('idle-blink','Parpadeo'),('ending-es-100ms','100 ms después de detener la voz ES')])
page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Isa · revisión de funcionalidades</title>
<style>body{font:16px/1.6 system-ui;background:#edf8fc;color:#123952;margin:24px}main{max-width:1100px;margin:auto}h1,h2{line-height:1.2}section{margin:36px 0}a{color:#1e6d93}.table{overflow-x:auto}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #b8dce9}th{white-space:nowrap}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}figure{margin:0}img{max-width:100%;height:auto;border-radius:8px}summary{cursor:pointer;padding:12px 0}.note{border-left:3px solid #3297b5;padding-left:16px}@media(max-width:600px){body{margin:12px}.gallery{grid-template-columns:1fr 1fr}th,td{min-width:140px;padding:8px}}</style>
<main><p>17 de noviembre de 2026 · revisión funcional local</p><h1>Isa: funciones verificadas y nuevas oportunidades</h1>
<p class="note">La base de reproducción funciona. Encontramos recuperación incompleta tras fallos, una lista de cierre distinta del catálogo corregido y cambios de boca más cortos que un frame. Ninguna corrección se aplicó a producción en esta revisión.</p>
<p>246 tests del backend y 38 de Isa en Angular pasaron. Se ensayó el retrato con sus recursos reales y se midió el reloj publicado sobre 32 WAV. Las cuatro skills aportaron análisis de voz, pausas, rostro y continuidad.</p>
<section><h2>Prioridades nuevas</h2><ol><li><strong>Reintentar la carga del atlas:</strong> si falló una vez, otra narración del mismo idioma no lo vuelve a cargar. Se reprodujo con un fallo controlado y posterior recuperación del recurso.</li>
<li><strong>Unificar referencias de reposo:</strong> al terminar, el renderer consulta otra lista; ES #123 figura cerrado y se ve abierto. #128 sigue incierto.</li>
<li><strong>Dar duración visual a los cambios:</strong> 22,2 % ES y 17,5 % EN de las marcas RF mapeadas duran menos de 41,7 ms. Eso no obliga a alargar todos los fonemas: hay que preservar cierres cortos importantes.</li>
<li><strong>Recuperar el mismo consejo:</strong> preparar replay/reintento explícito del audio y recuperación acotada de VOZ_OCUPADA, sin repetir Groq ni aceptar respuestas viejas.</li></ol></section>
<section><h2>Mapa de funciones</h2><div class="table"><table><thead><tr><th>Función</th><th>Estado</th><th>Evidencia / límite</th></tr></thead><tbody>TABLE</tbody></table></div></section>
<section><h2>Retrato real: poses y salida</h2><div class="gallery">CAPTURES</div><p>Las miradas lateral/abajo pueden ser «inciertas» para un detector que exige frente. Eso no las convierte en una animación defectuosa.</p></section>
<section><h2>Bocas que siguen pendientes</h2><p>Se revisaron los 34 casos a mayor resolución desde los MP4 originales. Aquí se muestran sin cambiarlos ni inventar fonemas. Los labios fruncidos necesitan una categoría/contexto propio; una imagen no identifica por sí sola el sonido.</p><details><summary>Ver las 34 bocas en resolución de origen</summary><a href="native-mouths/native-uncertain-mouths.png"><img src="native-mouths/native-uncertain-mouths.png" alt="34 bocas dudosas a resolución nativa"></a></details></section>
<section><h2>Voz y pausas</h2><p>Repetir Prosody Lens con umbral de 60 ms aumenta regiones candidatas: ES 1 → 13; EN 3 → 6 en los dos audios comparados. No son trece o seis silencios confirmados. Una consonante débil también puede parecer baja energía.</p>
<ul><li><a href="micro-prosody/es/report.html">Informe de micropausas ES</a></li><li><a href="micro-prosody/en/report.html">Informe de micropausas EN</a></li><li><a href="../skills-audit-v1/index.html">Relevamiento previo de las cuatro skills</a></li><li><a href="../visual-policy-review-v1/index.html">Última comparación visual con Random Forest</a></li></ul></section>
<section><h2>Resultados completos</h2><ul><li><a href="../../../experiments/isa_classifier/FUNCTIONALITY-AUDIT.md">Informe técnico y orden de trabajo</a></li><li><a href="functionality.json">Inventario y resultados JSON</a></li><li><a href="runtime-playback.json">Mediciones del reloj publicado</a></li><li><a href="portrait-functions.json">Reproducción del fallo de atlas y ciclo de vida</a></li></ul><p>RF y los nuevos selectores siguen siendo experimentales. La configuración real de Vercel/Render, dispositivos móviles reales y calidad auditiva humana no se verificaron aquí. Los informes de voz contienen audio de prueba local. No hubo consultas a Groq ni análisis externo.</p></section></main></html>'''
(root/'index.html').write_text(page.replace('TABLE',table).replace('CAPTURES',captures),encoding='utf8')
print(json.dumps({'functions':len(matrix),'backend_tests':246,'frontend_tests':38,'browser_checks':len(portrait['checks']),'index':str(root/'index.html')}))
