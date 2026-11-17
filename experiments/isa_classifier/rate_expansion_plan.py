"""Novel weather advice; split by phrase, never by generated rate variant."""
from narration import app_text

ADVICE = {
 'es': [
  'El viento cambia esta mañana. Sujetá las macetas y elegí una calle reparada para caminar.',
  'Después del chaparrón pueden quedar charcos. Usá calzado cerrado y cruzá despacio las veredas mojadas.',
  'Las nubes dejan algunos claros. Aprovechá un rato de luz para ventilar antes de que refresque.',
  'Si vas a pedalear, revisá las ráfagas del recorrido. Un casco bien ajustado ayuda durante la salida.',
  'La mañana empieza fresca, pero al mediodía cambia. Llevá una capa liviana que puedas guardar.',
  'Hoy el aire se siente húmedo. Dejá secar la ropa bajo techo si el cielo sigue cubierto.',
  'El parque puede tener barro después de la lluvia. Elegí senderos firmes para pasear.',
  'Guardá el paraguas cerca de la puerta. Las lluvias aisladas pueden sorprender durante un viaje corto.',
  'El cielo se despeja hacia la tarde. Revisá el pronóstico antes de organizar una merienda afuera.',
  'La brisa del balcón puede mover objetos pequeños. Guardá los papeles y asegurá las sillas plegables.',
  'Para una caminata corta, llevá agua y buscá sombra. El sol puede sentirse fuerte aunque haya nubes.',
  'La temperatura baja cuando se oculta el sol. Sumá un abrigo si volvés después de cenar.',
  'Antes de lavar el auto, mirá las próximas horas. Una lluvia breve podría cambiar tus planes.',
  'Hoy conviene llevar una bolsa impermeable. Te sirve para proteger el teléfono si empieza a lloviznar.',
  'El viento levanta polvo en caminos abiertos. Cerrá las ventanas que dan a la calle.',
  'Si salís con tu mascota, probá un paseo temprano. Después puede aumentar la sensación de calor.',
  'La neblina puede reducir la vista del paisaje. Dejá la foto panorámica para cuando mejore la visibilidad.',
  'Una tarde variable pide ropa práctica. Combiná una remera con un abrigo fácil de llevar.',
  'El agua de la lluvia tarda en secarse a la sombra. Prestá atención a las baldosas del patio.',
  'Para ir a la biblioteca, llevá una campera fina. Puede refrescar mientras estás estudiando.',
  'Una helada puede dejar escarcha en el jardín. Revisá tus plantas delicadas antes de regarlas.',
  'Si planeás mirar las estrellas, consultá la nubosidad nocturna. Buscá un lugar protegido de las ráfagas.',
  'El cambio de estación trae amplitud térmica. Prepará ropa para una mañana fría y una tarde templada.',
  'En la costa la brisa suele sentirse distinta. Revisá el viento local antes de desplegar una sombrilla.',
  'La terraza recibe mucho sol al mediodía. Organizá las tareas afuera para una hora más fresca.',
  'Las hojas mojadas pueden resbalar. Caminá con cuidado si el sendero está cubierto después de la tormenta.',
  'Para un viaje en colectivo, guardá un piloto liviano. Las paradas abiertas ofrecen poco reparo de la lluvia.',
  'Si aparece niebla al amanecer, esperá mejores condiciones para disfrutar de la vista desde el mirador.',
 ],
 'en': [
  'A gusty morning can move loose items. Secure balcony plants before you leave for work.',
  'Puddles may remain after the shower. Choose closed shoes and take your time on wet paths.',
  'Some breaks in the clouds could bring sunshine. Open a window briefly before the air turns cooler.',
  'Check the wind along your cycling route. Fast gusts can make an exposed path feel different.',
  'The day starts cool and warms up later. Wear a light layer that fits inside your bag.',
  'Humidity may keep clothes damp for longer. Use a sheltered drying spot if the sky stays cloudy.',
  'Recent rain can leave the park muddy. Pick a firm path for your afternoon walk.',
  'Keep a compact umbrella near the door. A short trip could overlap with an isolated shower.',
  'Clearer skies may arrive later today. Check the next few hours before planning an outdoor snack.',
  'A balcony breeze can scatter small objects. Put away loose papers and fold the spare chair.',
  'Bring some water for your walk. Cloud cover does not always mean the sunshine will feel weak.',
  'The air may cool quickly after sunset. Pack another layer if you expect to return late.',
  'Before washing the car, check the hourly forecast. A brief shower could change the plan.',
  'An extra waterproof bag can be useful today. Keep your phone dry if drizzle starts on the way.',
  'Dry wind can carry dust from open ground. Close the windows facing the street.',
  'An early pet walk may feel more comfortable. The afternoon could be warmer than the morning.',
  'Mist may hide distant hills for a while. Save the landscape photo for clearer conditions.',
  'Variable weather calls for flexible clothing. Pair a comfortable shirt with a jacket you can carry.',
  'Rainwater dries slowly in shaded corners. Watch the slippery tiles near your doorway.',
  'Take a thin jacket to the library. It may feel cooler by the time you finish studying.',
  'Frost may settle in the garden overnight. Check tender plants before watering them in the morning.',
  'For stargazing, look at the overnight cloud forecast. Choose a spot sheltered from stronger gusts.',
  'A large daily temperature range calls for layers. Be ready for a cold start and a mild afternoon.',
  'Coastal wind can feel stronger near the water. Check local conditions before opening a beach umbrella.',
  'The roof terrace gets direct midday sunshine. Plan outdoor chores for a cooler part of the day.',
  'Wet leaves can make a trail slippery. Walk carefully if the path is covered after a storm.',
  'A light raincoat can help on a bus trip. An uncovered stop offers little shelter from showers.',
  'Morning fog may hide the view from the lookout. Wait for clearer conditions before planning your visit.',
 ]}


def make_plan():
    rows = []
    for language, phrases in ADVICE.items():
        for i, advice in enumerate(phrases):
            split = 'train' if i < 16 else 'dev' if i < 20 else 'test'
            rows.append({'id': f'{language}-rate2-{i+1:02}', 'group_id': f'{language}-rate2-{i+1:02}',
                         'language': language, 'split': split, 'advice': advice,
                         'text': app_text(advice, language), 'evaluation': 'fresh'})
    return rows
