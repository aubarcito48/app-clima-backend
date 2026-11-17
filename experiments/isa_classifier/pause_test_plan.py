"""New pause-repair test phrases, excluded from all parameter selection."""
import json
from pathlib import Path
import sys
from narration import app_text
ADVICE = {
 'es': [
  'Para trabajar cerca de la ventana, mirá cómo cambia el viento. Guardá los papeles antes de abrirla.',
  'La lluvia de anoche puede dejar húmeda la madera. Revisá el banco antes de sentarte en el jardín.',
  'Si pasás la tarde leyendo afuera, llevá algo de abrigo. La sombra puede sentirse fresca después de un rato.',
  'Antes de salir a correr, consultá las ráfagas de la tarde. Un recorrido protegido puede ser más cómodo.',
  'Si el cielo sigue cubierto, la ropa puede tardar en secarse. Dejá espacio entre las prendas del tendedero.',
  'Un paseo con sol pide una gorra y agua. Elegí un horario tranquilo si esperás mucho calor.',
  'Las nubes pueden tapar el sol durante la merienda. Tené un abrigo liviano cerca de la mesa.',
  'Después de una llovizna, los escalones pueden seguir mojados. Mirá dónde apoyás los pies al bajar.',
 ],
 'en': [
  'Check how the wind changes before working beside an open window. Put loose papers away first.',
  'Overnight rain can leave wood damp. Check the garden bench before sitting down.',
  'Bring another layer if you plan to read outside all afternoon. A shaded corner may feel cool after a while.',
  'Before going for a run, check the afternoon gusts. A sheltered route may feel more comfortable.',
  'Clothes may dry slowly under a cloudy sky. Leave some space between items on the drying rack.',
  'Take a cap and water for a sunny walk. Choose a quieter hour if the day looks hot.',
  'Clouds may hide the sunshine during your outdoor snack. Keep a light jacket near the table.',
  'Steps can remain wet after a little drizzle. Watch where you place your feet as you go down.',
 ]}

def make_plan():
    return [{'id': f'{lang}-pause-test-{i+1:02}', 'group_id': f'{lang}-pause-test-{i+1:02}',
             'language': lang, 'split': 'test', 'evaluation': 'fresh', 'advice': advice,
             'text': app_text(advice, lang)} for lang, phrases in ADVICE.items() for i, advice in enumerate(phrases)]

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(make_plan(), ensure_ascii=False), encoding='utf8')
