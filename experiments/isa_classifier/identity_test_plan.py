"""New advice reserved only for the phoneme-identity experiment."""
import json
from pathlib import Path
import sys
from narration import app_text
ADVICE = {
 'es': [
  'Si vas a cruzar la plaza, buscá los caminos secos. Puede quedar agua bajo los árboles.',
  'Una mañana con cielo gris puede abrirse después. Mirá la nubosidad antes de sacar la bicicleta.',
  'Para llevar libros en la mochila, sumá una funda. Una llovizna corta también puede mojar el papel.',
  'El aire fresco de la noche cambia la sensación térmica. Cerrá las ventanas antes de acostarte.',
  'Un día de mucho viento no es ideal para colgar mantas afuera. Elegí un espacio cubierto.',
  'Si organizás un picnic, revisá las ráfagas previstas. Llevá algo que permita sujetar el mantel.',
  'Las primeras horas pueden ser más agradables para pasear. Después buscá un lugar con sombra.',
  'Las nubes bajas pueden ocultar las sierras. Consultá la visibilidad antes de elegir un recorrido panorámico.',
 ],
 'en': [
  'If you cross the square, choose a dry path. Water may remain beneath the trees.',
  'A grey morning might turn brighter later. Check the cloud forecast before taking your bicycle out.',
  'Protect the books inside your backpack with a cover. Even a little drizzle can leave paper wet.',
  'Cool night air can change how the temperature feels. Close the windows before going to bed.',
  'Strong wind can make hanging blankets outside awkward. Choose a covered space for drying them.',
  'Before arranging a picnic, check the expected gusts. Bring something to hold the tablecloth in place.',
  'The first hours of the day may feel better for a walk. Find some shade as it gets warmer.',
  'Low clouds may hide the hills from view. Check visibility before choosing a scenic route.',
 ]}

def make_plan():
    return [{'id': f'{lang}-identity-test-{i+1:02}', 'group_id': f'{lang}-identity-test-{i+1:02}',
             'language': lang, 'split': 'test', 'evaluation': 'fresh', 'advice': advice,
             'text': app_text(advice, lang)} for lang, phrases in ADVICE.items() for i, advice in enumerate(phrases)]

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(make_plan(), ensure_ascii=False), encoding='utf8')
