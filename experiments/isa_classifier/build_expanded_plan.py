"""V7: 96 fixed new app-style recordings, with sixteen final tests per voice."""

import argparse
import json
from pathlib import Path

from narration import app_text
from generate_corpus import validate_plan

ADVICE = {
 'es': {
  'train': [
   'Usá una blusa liviana. El aire cálido y húmedo hará pesado el paseo.',
   'Llevá un chaleco fino. La mañana fresca mejorará cuando salga el sol.',
   'Elegí pantalones cómodos. La brisa seca te acompañará durante la caminata.',
   'Ponete un piloto corto. Algunas gotas pueden sorprenderte al volver.',
   'Guardá un pañuelo abrigado. La ráfaga del sur se sentirá en el cuello.',
   'Usá zapatos ventilados. Hoy el ambiente será sofocante bajo el techo.',
   'Llevá un pulóver suave. Quedarte quieto al aire libre puede darte frío.',
   'Elegí una gorra liviana. El sol estará fuerte aunque veas algunas nubes.',
   'Ponete una capa impermeable. La lluvia débil puede continuar por varias horas.',
   'Usá un abrigo corto y cómodo. El cambio de viento refrescará el barrio.',
   'Llevá zapatillas secas de repuesto. Los charcos pueden mojarte durante el trayecto.',
   'Elegí una remera de algodón. La tarde estará calurosa y casi sin viento.',
   'Ponete una bufanda delgada. La sombra se sentirá fresca después de almorzar.',
   'Usá una chaqueta cerrada. Esta noche el viento puede atravesar prendas muy finas.',
   'Llevá un sombrero cómodo. Si esperás el colectivo al sol, buscá reparo.',
   'Elegí calzado antideslizante. El rocío puede dejar húmeda la entrada de casa.',
   'Ponete un buzo con cierre. Podrás abrirlo cuando mejore la temperatura.',
   'Usá una prenda térmica debajo. El frío de la madrugada seguirá unas horas.',
   'Llevá ropa liviana y agua. Con 29 grados, caminar rápido puede acalorarte.',
   'Elegí un abrigo resistente al agua. La lluvia y el frío llegarán juntos.',
   'Ponete guantes finos para pedalear. Las manos pueden enfriarse con la brisa.',
   'Usá una campera plegable. Si vuelve la lluvia, podrás cubrirte enseguida.',
   'Llevá una camiseta extra. El sol calentará, pero la vuelta será fresca.',
   'Elegí prendas holgadas. La humedad puede volver incómoda la ropa ajustada.'
  ],
  'dev': [
   'Llevá una capucha liviana. El viento puede mover el paraguas en las esquinas.',
   'Usá un conjunto fresco. Esta tarde no hará falta un abrigo pesado.',
   'Ponete zapatos cómodos y secos. La mañana nublada mantendrá fresco el suelo.',
   'Elegí un cuello abrigado. A primera hora se sentirá el aire helado.',
   'Llevá un saquito fino. Al caer el sol puede cambiar la sensación térmica.',
   'Usá una visera si vas al parque. Buscá sombra cuando el sol quede alto.',
   'Ponete una campera cómoda sobre el buzo. Podrás quitarte una capa más tarde.',
   'Elegí ropa que no retenga humedad. Habrá calor y una brisa muy débil.'
  ],
  'test': [
   'Usá una camisa fresca para salir. El ambiente cálido seguirá después de las cuatro.',
   'Llevá una chaqueta fina en la mochila. Puede refrescar mientras esperás afuera.',
   'Elegí botas bajas e impermeables. La llovizna dejará mojado el camino.',
   'Ponete un abrigo que cubra el pecho. La ráfaga fría se sentirá al caminar.',
   'Usá ropa liviana con mangas. Así podrás protegerte del sol sin acalorarte tanto.',
   'Llevá guantes y medias secas. La mañana estará fría incluso si no llueve.',
   'Elegí una capa fácil de guardar. El tiempo mejorará después del chaparrón.',
   'Ponete calzado cerrado para volver tarde. El aire nocturno bajará de temperatura.',
   'Usá un buzo delgado para la sombra. Al sol podrás sentirte más cómodo.',
   'Llevá una botella de agua y ropa ventilada. El calor aumentará durante el paseo.',
   'Elegí prendas que corten el viento. Evitá que la bufanda quede suelta.',
   'Ponete una campera seca antes de salir. La humedad hará más molesto el frío.',
   'Usá pantalón fresco y zapatillas cómodas. No hará falta sumar muchas capas.',
   'Llevá un impermeable liviano aunque salga el sol. Más tarde podrían volver las gotas.',
   'Elegí un abrigo fino para la vuelta. La brisa del anochecer puede sentirse fresca.',
   'Ponete un gorro cómodo si salís temprano. Con 7 grados, conviene cubrir las orejas.'
  ]
 },
 'en': {
  'train': [
   'Wear a thin blouse. Warm, damp air will make the walk feel muggy.',
   'Bring a light waistcoat. The cool morning should improve when the sun appears.',
   'Choose comfortable trousers. A dry breeze will follow you during the walk.',
   'Put on a short raincoat. A few drops may surprise you on the way back.',
   'Pack a warm neck warmer. Southerly gusts will feel cold around your neck.',
   'Wear well-ventilated shoes. Conditions will feel stifling indoors today.',
   'Bring a soft pullover. Sitting still outside could make you feel cold.',
   'Choose a lightweight cap. Sunshine will be strong despite a few clouds.',
   'Put on a waterproof layer. Light rain could continue for several hours.',
   'Wear a short, comfortable coat. A change in wind direction will cool the neighbourhood.',
   'Bring spare dry trainers. Puddles may soak your shoes during the journey.',
   'Choose a cotton T-shirt. The afternoon will be hot with hardly any wind.',
   'Put on a thin scarf. Shaded areas will feel cool after lunch.',
   'Wear a jacket you can fasten. Tonight the wind may cut through thin clothes.',
   'Bring a comfortable sunhat. Seek shelter when waiting for the bus in sunshine.',
   'Choose shoes with non-slip soles. Dew could leave your doorstep damp.',
   'Put on a zipped jumper. You can open it as temperatures improve.',
   'Wear a thermal layer underneath. The early morning cold will linger for a while.',
   'Bring light clothes and water. At 29 degrees, a fast walk can make you hot.',
   'Choose a water-resistant coat. Rain and cold weather will arrive together.',
   'Put on thin gloves for cycling. The breeze could chill your hands.',
   'Wear a packable jacket. You can cover up quickly if the rain returns.',
   'Bring an extra top. Sunshine will warm you up, but the trip home will be cooler.',
   'Choose loose-fitting clothes. Humidity can make tight layers uncomfortable.'
  ],
  'dev': [
   'Bring a lightweight hood. Wind around street corners could shake your umbrella.',
   'Wear a cool outfit. You should not need a heavy coat this afternoon.',
   'Put on dry, comfortable shoes. The cloudy morning will keep the ground cool.',
   'Choose a warm neck covering. The air will feel icy first thing.',
   'Bring a thin cardigan. It may feel noticeably cooler as the sun goes down.',
   'Wear a visor at the park. Find shade when the sun is high.',
   'Put a comfortable jacket over your jumper. You can remove a layer later.',
   'Choose clothes that let moisture escape. It will be warm with very little breeze.'
  ],
  'test': [
   'Wear a cool shirt outdoors. The warm conditions will continue after four o’clock.',
   'Pack a thin jacket in your bag. It may get chilly while you wait outside.',
   'Choose low waterproof boots. Drizzle will leave the path wet.',
   'Put on a coat that covers your chest. Cold gusts will be noticeable as you walk.',
   'Wear light clothes with sleeves. They can protect you from sunlight without feeling too warm.',
   'Bring gloves and dry socks. The morning will be cold even without rain.',
   'Choose a layer that packs away easily. Conditions should improve after the shower.',
   'Put on closed shoes if you return late. The night air will become cooler.',
   'Wear a thin jumper in the shade. You may feel more comfortable in sunshine.',
   'Bring a water bottle and breathable clothes. The heat will increase during your walk.',
   'Choose clothes that block the wind. Keep your scarf from hanging loose.',
   'Put on a dry jacket before leaving. Damp air will make the cold more unpleasant.',
   'Wear thin trousers and comfortable trainers. You will not need many layers.',
   'Bring a light raincoat despite the sunshine. More drops could arrive later.',
   'Choose a light coat for the return journey. The evening breeze may feel fresh.',
   'Put on a comfortable hat if you leave early. At 7 degrees, covering your ears will help.'
  ]
 }
}


def make_additions():
    rows = [{'id': f'{language}-v7-{split}-{index:02d}', 'language': language, 'split': split,
             'advice': advice, 'text': app_text(advice, language)}
            for language, splits in ADVICE.items() for split, phrases in splits.items()
            for index, advice in enumerate(phrases, 1)]
    plan = {'version': 1, 'reference': 'weak-rhubarb', 'narration_profile': 'app-greeting-v1', 'recordings': rows}
    validate_plan(plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = make_additions()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and json.loads(args.output.read_text(encoding='utf8')) != plan:
        parser.error('Use a new path for a changed experiment')
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'new_recordings': len(plan['recordings'])}))
