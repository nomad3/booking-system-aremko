import requests

def enviar_reserva_manychat(cliente, reserva):
    url = 'https://api.manychat.com/fb/some-endpoint'  # URL del API de ManyChat
    headers = {'Authorization': 'Bearer TU_TOKEN_DE_MANYCHAT'}
    data = {
        'subscriber_id': cliente.id,
        'message': {
            'text': f'Hola {cliente.nombre}, tu reserva ha sido confirmada desde el {reserva.fecha_inicio} al {reserva.fecha_fin}.'
        }
    }
    requests.post(url, json=data, headers=headers)
