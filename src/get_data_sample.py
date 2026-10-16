import requests

DATA_ENDPOINT = 'https://data.elexon.co.uk/bmrs/api/v1/demand/outturn/summary'
def get_sample_data(endpoint: str, params: dict):
    res = requests.get(
        url=endpoint,
        params=params,
        timeout=30
    )
    
    res.raise_for_status()
    
    data = res.json()
    
    return data


if __name__ == '__main__':
    params = {
        'from': '2024-07-14T00:00:00Z',
        'to': '2024-07-15T00:00:00Z',
        'format': 'json'
    }
    
    sample_data = get_sample_data(
        endpoint=DATA_ENDPOINT,
        params=params
    )
    
    print(type(sample_data))
    print(len(sample_data))
    print(sample_data[0])