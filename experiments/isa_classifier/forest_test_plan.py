"""Fresh advice reserved for the Random Forest/XGBoost comparison."""
import json
from pathlib import Path
import sys
from narration import app_text
ADVICE = {
 'es': [
  'Antes de dejar la bici afuera, mirá si viene lluvia. Una cubierta puede ayudar a mantener seco el asiento.',
  'Si preparás café en el patio, buscá reparo del viento. Una mesa protegida hace más cómodo el descanso.',
  'La humedad puede empañar un vidrio frío. Ventilá un momento si el clima de afuera lo permite.',
  'Para ir a la feria, llevá una bolsa que puedas cerrar. Un chaparrón breve podría sorprenderte a la vuelta.',
  'Si se despeja por la noche, puede sentirse más fresco. Tené una manta liviana cerca del sillón.',
  'La brisa de la mañana puede refrescar el comedor. Abrí un poco y revisá que no vuelen papeles.',
  'Si caminás hasta la estación, revisá el pronóstico por hora. Un piloto pequeño ocupa poco lugar en la mochila.',
  'Después de la tormenta, puede quedar agua en las macetas. Miralas antes de volver a regar las plantas.',
 ],
 'en': [
  'Check for rain before leaving your bike outside. A cover can help keep the seat dry.',
  'If you make coffee on the patio, find shelter from the wind. A protected table makes the break more comfortable.',
  'Humidity can fog a cold window. Ventilate briefly if the weather outside allows it.',
  'Bring a bag you can close when visiting the market. A short shower might catch you on the way back.',
  'A clear night may feel cooler. Keep a light blanket close to the sofa.',
  'The morning breeze may cool the dining room. Open the window slightly and keep loose papers secure.',
  'Check the hourly forecast before walking to the station. A small raincoat takes little space in your backpack.',
  'Water may remain inside flowerpots after a storm. Check them before watering the plants again.',
 ]}

def make_plan():
    return [{'id': f'{lang}-forest-test-{i+1:02}', 'group_id': f'{lang}-forest-test-{i+1:02}',
             'language': lang, 'split': 'test', 'evaluation': 'fresh', 'advice': advice,
             'text': app_text(advice, lang)} for lang, phrases in ADVICE.items() for i, advice in enumerate(phrases)]

if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(make_plan(), ensure_ascii=False), encoding='utf8')
