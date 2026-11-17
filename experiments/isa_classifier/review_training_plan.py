"""Fixed grouped expansion, written before synthesis and model selection."""
import json
import sys
from pathlib import Path
from narration import app_text

ADVICE = {
 'es': [
  'Si vas a pintar una maceta afuera, buscá un rato sin viento. Tapá el pincel cuando termines.',
  'Antes de pasear al perro, mirá cómo viene la tarde. Una bolsa pequeña protege el teléfono si llueve.',
  'La brisa puede mover las servilletas del balcón. Poné un peso liviano y cerrá bien la puerta.',
  'Para esperar el colectivo temprano, llevá una bufanda fina. Podés guardarla si después sale el sol.',
  'Si la ropa sigue húmeda, separá las prendas en el tender. Dejá espacio para que pase el aire.',
  'Una nube oscura puede traer un chaparrón corto. Revisá el cielo antes de sacar los almohadones.',
  'Si preparás pan para una salida, guardalo en una bolsa cerrada. Elegí un lugar con sombra para descansar.',
  'Después de una mañana fresca, la plaza puede sentirse más cálida. Llevá agua y buscá sombra al mediodía.',
  'La ventana del baño puede quedar empañada. Abrila unos minutos si afuera no hay lluvia ni viento fuerte.',
  'Para caminar junto al río, revisá el viento antes de salir. Ajustá la gorra y llevá una campera liviana.',
  'Si el sol aparece entre las nubes, el patio puede calentarse. Mové las plantas delicadas hacia la sombra.',
  'Antes de volver en bici, fijate si cambió el tiempo. Guardá los papeles sueltos dentro de la mochila.',
  'Si merendás junto a una ventana abierta, revisá la brisa. Acercá la taza y alej ale los papeles del borde.'.replace('alej ale','alejá'),
  'Las baldosas pueden seguir mojadas después de llover. Caminá con calma y elegí un calzado que agarre bien.',
  'Una tarde ventosa puede secar rápido las toallas. Sujetalas bien antes de dejarlas afuera.',
  'Para salir con una manta de picnic, esperá un lugar seco. Revisá el pronóstico antes de preparar la comida.',
  'Si llevás una guitarra al parque, buscá sombra. Guardala si aparecen gotas o cambia mucho el viento.',
  'La vereda puede enfriarse al anochecer. Sumá una capa liviana si vas a esperar afuera un buen rato.',
  'Si vas al vivero, revisá si lloverá durante la vuelta. Una caja firme ayuda a transportar las plantas.',
  'Antes de abrir el techo del auto, mirá las nubes. Cerralo si se acerca lluvia o aumenta el viento.',
  'Si preparás una mesa en la terraza, sujetá el mantel. Tené un lugar cubierto por si cambia la tarde.',
  'Una mañana con niebla puede sentirse húmeda. Llevá abrigo liviano y salí con tiempo para caminar tranquilo.',
  'Si salís a fotografiar flores, protegé la cámara de las gotas. Buscá reparo cuando sople el viento.',
  'Después de un día cálido, la noche puede refrescar. Dejá un buzo cerca antes de sentarte en el jardín.',
 ],
 'en': [
  'If you paint a flowerpot outside, choose a calm spell. Cover the brush when you finish.',
  'Check the afternoon weather before walking the dog. A small bag can protect your phone from rain.',
  'A breeze can lift napkins from the balcony table. Add a light weight and close the door firmly.',
  'Take a thin scarf when waiting for an early bus. Put it away if the sun comes out later.',
  'If the washing is still damp, spread the clothes apart. Leave room for air to pass between them.',
  'A dark cloud may bring a brief shower. Check the sky before putting the cushions outside.',
  'Pack bread in a closed bag for your outing. Choose a shady place when you stop for a break.',
  'The square may feel warmer after a cool morning. Bring water and find shade around midday.',
  'The bathroom window may stay foggy. Open it briefly if there is no rain or strong wind outside.',
  'Check the wind before walking beside the river. Secure your cap and bring a light jacket.',
  'Sun between the clouds may warm the patio. Move delicate plants into the shade when needed.',
  'Check for a weather change before cycling home. Put loose papers safely inside your backpack.',
  'Check the breeze when having a snack near an open window. Move your cup and papers away from the edge.',
  'Paving stones may stay wet after rain. Walk slowly and choose shoes with a firm grip.',
  'A windy afternoon can dry towels quickly. Secure them carefully before leaving them outside.',
  'Choose a dry spot for your picnic blanket. Check the forecast before packing the food.',
  'Find shade if you take a guitar to the park. Put it away if drops appear or the wind changes.',
  'The pavement can feel cooler after sunset. Add a light layer if you will be waiting outdoors.',
  'Check for rain before visiting the plant nursery. A sturdy box helps carry your plants home.',
  'Look at the clouds before opening the car roof. Close it if rain approaches or the wind picks up.',
  'Secure the tablecloth when setting a terrace table. Keep a covered spot ready in case the weather changes.',
  'A foggy morning may feel damp. Take a light coat and allow time for an easy walk.',
  'Protect your camera from drops when photographing flowers. Find shelter when the wind starts blowing.',
  'The night may turn cool after a warm day. Keep a sweater nearby before sitting in the garden.',
 ]}

def make_plan():
 rows=[]
 for language, phrases in ADVICE.items():
  for i, advice in enumerate(phrases):
   split='train' if i<12 else 'dev' if i<16 else 'test'
   group=f'{language}-review-v2-{split}-{i+1:02}'
   text=app_text(advice,language)
   assert len(text)<=280 and len(advice.split())<=40
   rows.append(dict(id=group,group_id=group,language=language,split=split,
                    evaluation='fresh',advice=advice,text=text))
 return rows

if __name__=='__main__':
 Path(sys.argv[1]).write_text(json.dumps(make_plan(),ensure_ascii=False,indent=2),encoding='utf8')
