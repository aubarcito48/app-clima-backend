"""Fixed short weather advice corpus, with the app greeting/farewell in every WAV."""

import argparse
import json
from pathlib import Path

from narration import app_text
from generate_corpus import validate_plan

ADVICE = {
 'es': {
  'train': [
   'Usá una remera fresca y calzado abierto. Hoy el calor se mantiene hasta la tarde.',
   'Llevá un buzo liviano. El viento fresco puede sentirse al volver a casa.',
   'Elegí una campera impermeable y zapatillas cerradas. Habrá chaparrones durante la mañana.',
   'Ponete guantes y una bufanda. La sensación térmica estará por debajo de cero.',
   'Usá ropa clara y un sombrero. Si caminás al sol, buscá sombra y tomá agua.',
   'Llevá una capa extra para la noche. Después del atardecer baja bastante la temperatura.',
   'Elegí calzado con buena suela. La llovizna puede dejar resbaladizas las veredas.',
   'Una camisa liviana va bien hoy. Guardá un abrigo fino para los lugares con aire acondicionado.',
   'Usá una campera que corte el viento. Sujetá bien la gorra si salís a caminar.',
   'Llevá un paraguas pequeño. Puede llover un rato y luego volver el sol.',
   'Ponete medias abrigadas y zapatos secos. La humedad hará que se sienta más frío.',
   'Elegí prendas cómodas y ventiladas. Con 31 grados, evitá salir al mediodía.',
   'Usá varias capas finas. Podrás quitarte una si el sol calienta más tarde.',
   'Llevá botas impermeables. Evitá cruzar por donde se acumule agua.',
   'Una chaqueta ligera alcanza para salir. Más tarde refresca cerca del río.',
   'Usá abrigo y cubrite las orejas. Con 4 grados y ráfagas, el frío se nota más.'
  ],
  'dev': [
   'Llevá una campera con capucha. Las lluvias aisladas pueden alcanzarte al salir del trabajo.',
   'Usá pantalón liviano y una remera suelta. El ambiente seguirá cálido durante varias horas.',
   'Elegí zapatillas resistentes al agua. Si seguís afuera al anochecer, sumá un buzo.',
   'Ponete un abrigo cómodo. Las nubes y el viento mantendrán fresca la mañana.'
  ],
  'test': [
   'Llevá un saco liviano y calzado cerrado. Con 17 grados, la brisa puede molestar en la sombra.',
   'Usá ropa que se seque rápido. Los chaparrones serán breves, pero pueden mojarte bastante.',
   'Ponete una campera gruesa y guantes. Si salís temprano, el aire frío puede sentirse intenso.',
   'Elegí ropa suelta y protegé la cabeza del sol. Cuando refresque, agregá una capa fina.'
  ]
 },
 'en': {
  'train': [
   'Wear a cool T-shirt and open shoes. The heat will last through the afternoon.',
   'Bring a light jumper. You may notice the cool breeze on your way home.',
   'Choose a waterproof jacket and closed shoes. Showers are expected this morning.',
   'Put on gloves and a scarf. It will feel colder than zero degrees outside.',
   'Wear light colours and a hat. Find shade and drink water when walking in the sun.',
   'Pack an extra layer for tonight. Temperatures will drop after sunset.',
   'Choose shoes with a firm grip. Drizzle could make the pavements slippery.',
   'A thin shirt works well today. Keep a light layer for air-conditioned rooms.',
   'Wear a windproof coat. Hold on to your hat if you go for a walk.',
   'Take a small umbrella. A short shower may be followed by sunshine.',
   'Put on warm socks and dry shoes. Damp air will make it feel colder.',
   'Choose loose, breathable clothes. At 31 degrees, avoid heading out around midday.',
   'Wear several thin layers. You can remove one when the sun warms up later.',
   'Take waterproof boots. Avoid walking through patches of standing water.',
   'A light jacket should be enough outdoors. It will feel cooler near the river later.',
   'Wear a warm coat and cover your ears. At 4 degrees, gusts make the cold more noticeable.'
  ],
  'dev': [
   'Bring a hooded jacket. Isolated showers could catch you as you leave work.',
   'Wear thin trousers and a loose top. Conditions will stay warm for several hours.',
   'Choose water-resistant trainers. Add a jumper if you stay outside after dark.',
   'Put on a comfortable coat. Clouds and wind will keep the morning cool.'
  ],
  'test': [
   'Bring a light coat and closed shoes. At 17 degrees, the breeze may feel chilly in the shade.',
   'Wear clothes that dry quickly. Showers will be short, but they could leave you quite wet.',
   'Put on a thick jacket and gloves. The cold air may feel harsh if you leave early.',
   'Choose loose clothes and protect your head from the sun. Add a thin layer when it cools down.'
  ]
 }
}


def make_plan():
    rows = []
    for language, splits in ADVICE.items():
        for split, phrases in splits.items():
            for index, advice in enumerate(phrases, 1):
                rows.append({'id': f'{language}-v6-{split}-{index:02d}', 'language': language,
                             'split': split, 'advice': advice, 'text': app_text(advice, language)})
    plan = {'version': 1, 'reference': 'weak-rhubarb', 'narration_profile': 'app-greeting-v1', 'recordings': rows}
    validate_plan(plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = make_plan()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and json.loads(args.output.read_text(encoding='utf8')) != plan:
        parser.error('Use a new plan path instead of overwriting a different experiment')
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'plan': str(args.output), 'new_recordings': len(plan['recordings'])}))
