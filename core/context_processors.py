from .geolocation import get_client_currency, get_currency_display_info, detect_country_from_request


def geo_currency_context(request):
    """
    Context processor global que disponibiliza a moeda e o país detectados por geolocalização
    em todos os templates Django.
    """
    currency = get_client_currency(request)
    display_info = get_currency_display_info(currency)
    country_code = detect_country_from_request(request)

    return {
        'geo_currency': currency,
        'geo_currency_symbol': display_info['symbol'],
        'geo_currency_flag': display_info['flag'],
        'geo_country_code': country_code,
    }
