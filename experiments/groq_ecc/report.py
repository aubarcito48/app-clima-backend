"""Report API measurements without equating schema validity with advice quality."""
import html
import json
from pathlib import Path
import sys

def main():
    folder=Path(sys.argv[1]);data=json.loads((folder/'results.json').read_text(encoding='utf8'))
    if data['status']!='complete':raise RuntimeError('Benchmark incomplete')
    before=data['summary']['groq'];after=data['summary']['local']
    incoming=1-after['prompt_tokens']/before['prompt_tokens']
    outgoing=1-after['completion_tokens']/before['completion_tokens']
    total=1-(after['prompt_tokens']+after['completion_tokens'])/(before['prompt_tokens']+before['completion_tokens'])
    reported=[r for r in data['rows'] if isinstance(r['usage'].get('prompt_tokens_details'),dict)]
    rejected=[{'scenario':r['scenario'],'language':r['language'],'arm':r['arm'],'phase':r['phase']} for r in data['rows'] if not r['valid']]
    summary={'same_model':data['model'],'ecc_installed':False,'paired_cases_per_arm':before['requests'],
      'real_attempts':data['real_requests'],'successful_requests':len(data['rows']),
      'input_token_reduction':incoming,'output_token_reduction':outgoing,'total_token_reduction':total,
      'cache_metric_reported_requests':len(reported),'cache_test':data['cache_test'],
      'rejected_responses':rejected,
      'provider_cached_tokens':sum(r['cached_prompt_tokens'] for r in data['rows']),
      'provider_requests_with_cached_tokens':sum(r['cached_prompt_tokens']>0 for r in data['rows']),
      'recommendation':'No ECC runtime needed. Keep current model; response-cache pattern useful for repeated unchanged inputs. Local direction needs further quality review.'}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    notes='''El ahorro de tokens está medido. La calidad del mensaje no queda demostrada por la validación JSON.
En frío español, el director local produjo «sin abrigo ni chaqueta, porque hace frío» con 3 °C:
es un consejo contradictorio y además incumple el vocabulario regional pedido.
El modo actual también produjo recomendaciones que requieren revisión, como ropa ligera con frío.
No se concluye que el modelo local sea peor en general a partir de una salida; sí impide afirmar
que el cambio conserva la calidad. No se cambia el modelo ni el director de producción.
La caché completa reutiliza la misma respuesta sólo con contexto, idioma y parámetros idénticos
y vigencia de 300 s. Los dos aciertos de cuatro consultas son de un escenario construido para
repetir: no representan la tasa de aciertos de la aplicación real.
El tiempo de espera para respetar la cuota no está incluido en la latencia de cada API call.
Una tanda pequeña, parcialmente reanudada, no demuestra una mejora general de latencia.'''
    table='''| Modo | Respuestas válidas por parser | Tokens entrada | Tokens salida | Mediana API (s) |
| --- | ---: | ---: | ---: | ---: |
'''+''.join(f"| {name} | {r['valid']}/{r['requests']} | {r['prompt_tokens']} | {r['completion_tokens']} | {r['median_wall_seconds']:.3f} |\n" for name,r in [('Actual / director Groq',before),('Mismo modelo / director local',after)])
    text=f'''# Evaluación de patrones ECC con Groq

Modelo sin cambios: {data['model']}. ECC no fue instalado. No se modificó producción.
Se compararon cuatro climas en español e inglés, con la misma reserva de salida y razonamiento.

{table}
Reducción de entrada: {incoming:.1%}; salida: {outgoing:.1%}; tokens totales: {total:.1%}.
Los tokens de salida incluyen los de razonamiento informados por Groq. Esto no es un porcentaje
de ahorro monetario: entrada, salida y tokens cacheados pueden tener precios distintos.

Se completaron {len(data['rows'])} consultas reales, más un intento limitado por HTTP 429.
La tanda se reanudó sin repetir casos exitosos, espaciando consultas 22 s.
Respuestas con métricas de caché de prefijo informadas: {len(reported)}.
Tokens de entrada servidos desde caché nativa: {summary['provider_cached_tokens']},
en {summary['provider_requests_with_cached_tokens']} respuestas. Esa caché es de Groq y no necesitó ECC.
El proveedor no siempre informó el campo de caché; un campo ausente no prueba un acierto.
Respuestas rechazadas por el parser, contando todas las fases: {len(rejected)}.
La tabla principal sólo incluye las ocho parejas A/B, no las repeticiones adicionales.
La prueba de caché completa hizo {data['cache_test']['real_requests']} llamadas para
{data['cache_test']['logical_requests']} consultas y tuvo {data['cache_test']['hits']} aciertos.

## Calidad y decisión

{notes}

ECC aporta una guía de patrones, no un acelerador de Groq que deba instalarse en Render.
No se justifica instalar su conjunto completo para estos cambios. La práctica de caché
es útil; el director local ya existía y necesita evaluación adicional antes de adoptarlo.

Fuentes:
- https://github.com/affaan-m/ECC/blob/main/skills/cost-aware-llm-pipeline/SKILL.md
- https://console.groq.com/docs/prompt-caching
'''
    (folder/'report.md').write_text(text,encoding='utf8')
    samples=[]
    for row in data['rows']:
        if row['phase']!='paired':continue
        samples.append('<article><h3>'+html.escape(f"{row['scenario']} · {row['language']} · {row['arm']}")+'</h3><p>'+html.escape((row['advice'] or {}).get('texto','Respuesta rechazada por el parser'))+'</p></article>')
    page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Groq · evaluación de prácticas ECC</title><style>body{font:16px/1.6 system-ui;background:#edf8fc;color:#123952;max-width:1100px;margin:24px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border:1px solid #8bb6ca;border-radius:8px;padding:16px}section{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:650px){section{grid-template-columns:1fr}}</style><h1>Groq · ¿aporta ECC una mejora real?</h1><pre>'''+html.escape(text)+'''</pre><h2>Mensajes reales de las pruebas</h2><section>'''+''.join(samples)+'''</section></html>'''
    (folder/'index.html').write_text(page,encoding='utf8')
    print(json.dumps(summary))

if __name__=='__main__':main()
