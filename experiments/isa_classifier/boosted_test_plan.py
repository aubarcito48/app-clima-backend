"""Fresh advice held out from all previous model/parameter selection."""
import json
from pathlib import Path
import sys
from narration import app_text
ADVICE = {
 'es': [
  'La brisa puede mover la puerta del balcón. Dejala bien sujeta antes de salir a comprar.',
  'Si pintás una maceta afuera, revisá la humedad. Quizás tarde más en secarse de lo que esperabas.',
  'Antes de preparar la mesa en el patio, mirá las próximas lluvias. Un reparo cercano puede ayudarte.',
  'Un paseo por la rambla puede sentirse fresco. Llevá una prenda cómoda que corte el viento.',
  'Para esperar a alguien en la plaza, buscá sombra. El banco bajo el árbol puede ser más agradable.',
  'Las ráfagas pueden mover la cortina de la ventana. Cerrala un poco si tenés papeles sobre el escritorio.',
  'Si salís a fotografiar flores, fijate en el viento. Una mañana tranquila puede facilitar las fotos.',
  'El piso del quincho puede seguir húmedo después de la lluvia. Revisalo antes de mover las sillas.',
 ],
 'en': [
  'A breeze may push the balcony door around. Secure it before leaving to buy groceries.',
  'If you paint a flowerpot outdoors, check the humidity. It might take longer to dry than expected.',
  'Check the next showers before setting the patio table. A sheltered spot nearby could be useful.',
  'A walk beside the water may feel cool. Bring a comfortable layer that blocks the wind.',
  'If you are waiting for a friend in the square, find some shade. A bench beneath a tree may feel better.',
  'Gusts can move the curtain beside an open window. Close it slightly if papers are lying on your desk.',
  'Before photographing flowers outside, check the wind. A calm morning may make close pictures easier.',
  'The floor of a covered patio may stay wet after rain. Check it before moving the chairs.',
 ]}

def make_plan():
    return [{'id': f'{lang}-boosted-test-{i+1:02}', 'group_id': f'{lang}-boosted-test-{i+1:02}',
             'language': lang, 'split': 'test', 'evaluation': 'fresh', 'advice': advice,
             'text': app_text(advice, lang)} for lang, phrases in ADVICE.items() for i, advice in enumerate(phrases)]

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(make_plan(), ensure_ascii=False), encoding='utf8')
