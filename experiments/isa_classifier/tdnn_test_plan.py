"""Unseen final phrases for the fixed small temporal neural experiment."""
import json
from pathlib import Path
import sys
from narration import app_text

ADVICE = {
 'es': [
  'Si llevás libros al parque, guardalos en una funda. Algunas gotas pueden llegar antes de que encuentres reparo.',
  'Una tarde nublada puede ser agradable para pasear al perro. Llevá agua y revisá si aumenta el viento.',
  'Antes de salir con el cochecito, mirá la temperatura. Una capa liviana puede ayudar cuando cae el sol.',
  'El piso del balcón puede seguir mojado aunque ya no llueva. Caminá con cuidado y esperá antes de sacar almohadones.',
  'Si vas a tomar el colectivo temprano, prepará un abrigo fino. La espera puede sentirse fresca a la sombra.',
  'En un día seco, las plantas pequeñas pueden necesitar atención. Revisá la tierra antes de agregar más agua.',
  'Un viento fuerte puede mover la sombrilla. Cerrala antes de entrar y asegurá los objetos livianos de la terraza.',
  'Si salís a fotografiar el atardecer, revisá las nubes. Llevá una bolsa para proteger la cámara de una lluvia inesperada.',
 ],
 'en': [
  'Keep your books in a sleeve when visiting the park. A few drops may arrive before you find shelter.',
  'A cloudy afternoon can be pleasant for walking the dog. Bring water and check whether the wind is picking up.',
  'Check the temperature before going out with the stroller. A light layer may help after sunset.',
  'The balcony floor may stay wet after the rain stops. Walk carefully and wait before bringing out the cushions.',
  'Prepare a thin coat if you catch an early bus. Waiting in the shade may feel chilly.',
  'Small plants may need attention on a dry day. Check the soil before adding more water.',
  'Strong wind can move a patio umbrella. Close it before going inside and secure light objects on the terrace.',
  'Check the clouds before photographing the sunset. Bring a bag to protect your camera from unexpected rain.',
 ]}

def make_plan():
    return [{'id': f'{lang}-tdnn-test-{i+1:02}', 'group_id': f'{lang}-tdnn-test-{i+1:02}',
             'language': lang, 'split': 'test', 'evaluation': 'fresh', 'advice': advice,
             'text': app_text(advice, lang)} for lang, phrases in ADVICE.items() for i, advice in enumerate(phrases)]

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(make_plan(), ensure_ascii=False), encoding='utf8')
