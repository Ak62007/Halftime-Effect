import pandas as pd

def api_data_return_check(data: list[dict], start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """Does some checks on the data return by the api, checks for duplicates, missing values and more

    Args:
        data (dict): raw data received from the api
        start_utc (pd.Timestamp): start day date in utc.
        end_utc (pd.Timestamp): end day date in utc

    Returns:
        pd.DataFrame: checks the data and return it as a dataframe
        dict: keeps the records for all the checks
    """
    checks = {}
    # convert it into dataframe
    try:
        print('Converting the data into a dataframe...')
        data = pd.DataFrame(data)
    except Exception as e:
        raise Exception(f"Failed to convert data into DataFrame: {e}") from e
    else:
        print('Sucessfully converted!')
        
    
    # converting the startTime column in a UTC time stamp
    try:
        print('Converting the startTime column in a UTC time stamp...')
        data['startTime'] = pd.to_datetime(data['startTime'], utc=True)
        checks['null_timestamp_count_before_filter'] = data['startTime'].isna().sum()
    except Exception as e:
        raise Exception(f"Failed to convert the startTime column in a UTC time stamp: {e}") from e
    else:
        print('Successfully converted!')
    
    # removing the last index and sorting
    try:
        print('Removing the last index and sorting...')
        data = (data
                .loc[(data['startTime'] >= start_utc) & (data['startTime'] < end_utc)]
                .sort_values(by='startTime')
                )
    except Exception as e:
        raise Exception(f'Failed to remove the last and sort the data: {e}') from e
    
    
    # check unexpected timestamps, duplicates, 
    print("Checking unexpected timestamps...")
    expected = pd.date_range(
        start=start_utc,
        end=end_utc,
        freq='5min',
        inclusive='left'
    )
    
    actual = pd.DatetimeIndex(data['startTime'])
    
    missing = expected.difference(actual)
    unexpected = actual.difference(expected)
    
    gaps = data['startTime'].diff().dropna()
    
    checks['expected_no_of_rows'] = len(expected)
    checks['actual_no_of_rows'] = len(actual)
    checks['missing_timestamp_count'] = len(missing)
    checks['unexpected_timestamp_count'] = len(unexpected)
    checks['null_demand_count'] = len(data.loc[data['demand'].isna()])
    checks['demand_is_numeric'] = pd.api.types.is_numeric_dtype(data['demand'])
    checks['record_type_counts'] = data['recordType'].value_counts(dropna=False).to_dict()
    checks['gaps_five_mins'] = (len(data) >= 2 and gaps.eq(pd.Timedelta(minutes=5)).all())
    checks['duplicate_timestamp_count'] = data['startTime'].duplicated().sum()
    
    return (data, checks)