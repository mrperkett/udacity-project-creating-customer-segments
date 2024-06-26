import collections
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def parse_missing_or_unknown_str(missing_or_unknown_str):
    """
    Parse into a list the missing/unknown string from the "missing_or_unknown" column in
    AZDIAS_Feature_Summary.csv.

    Args:
        missing_or_unknown_str: the string signifying which values are unknown or missing in
                AZDIAS_Feature_Summary.csv.  Ex: "[-1,0]"
    
    Return:
        converted_list: a list of all values that signifiy missing or unknown.  If possible,
                the values will be converted to an int, but left as a string otherwise.
    """
    # unique missing_or_unknown: ['[-1,0]' '[-1,0,9]' '[0]' '[-1]' '[]' '[-1,9]' '[-1,X]' '[XX]' '[-1,XX]']
    if not missing_or_unknown_str.startswith("["):
        raise ValueError(f"missing_or_unknown_str ({missing_or_unknown_str}) is expected to start with '['")
    if not missing_or_unknown_str.endswith("]"):
        raise ValueError(f"missing_or_unknown_str ({missing_or_unknown_str}) is expected to end with ']'")
    
    split_list = missing_or_unknown_str[1:-1].split(",")
    converted_list = []
    for value in split_list:
        try:
            value = int(value)
        except:
            pass
        converted_list.append(value)
    return converted_list


def build_column_to_missing_and_unkown_values(df_feature_summary):
    """
    Build a dictionary mapping from column name to a list of values signifying missing/unknown.

    Args:
        df_feature_summary: pandas dataframe loaded from AZDIAS_Feature_Summary.csv.

    Return:
        column_to_missing_and_unkown_values
    """
    column_to_missing_and_unkown_values = dict()
    for _, row in df_feature_summary.iterrows():
        missing_or_unknown_str = row["missing_or_unknown"]
        column = row["attribute"]
        missing_or_unknown_list = parse_missing_or_unknown_str(missing_or_unknown_str)
        
        if column in column_to_missing_and_unkown_values:
            raise ValueError(f"column ({column}) is repeated within df_feature_summary")
        column_to_missing_and_unkown_values[column] = missing_or_unknown_list
    return column_to_missing_and_unkown_values


def build_column_to_data_type(df_feature_summary):
    """
    Build a dictionary mapping from column name to the column's data type.

    Args:
        df_feature_summary: pandas dataframe loaded from AZDIAS_Feature_Summary.csv.
    
    Return:
        column_to_data_type
    """
    column_to_data_type = dict()
    for _, row in df_feature_summary.iterrows():
        data_type = row["type"]
        column = row["attribute"]
        
        if column in column_to_data_type:
            raise ValueError(f"column ({column}) is repeated within df_feature_summary")
        column_to_data_type[column] = data_type
    return column_to_data_type


def set_missing_and_unknown_to_nan(input_df, column_to_missing_and_unkown_values):
    """
    Set all missing / unknown values to NaN

    Args:
        input_df: pandas dataframe loaded from Udacity_AZDIAS_Subset.csv
    
    Return:
        df: pandas dataframe with NaN added in place of missing / unknown data signifiers
    """
    # Reference for why I'm using pd.NA below
    # https://pandas.pydata.org/docs/user_guide/missing_data.html

    # check whether there are any columns that do not have a missing and unknown value list
    columns_missing = set(input_df.columns) - set(column_to_missing_and_unkown_values.keys())
    if columns_missing != set():
        raise ValueError(f"There are columns that do not have a list of values that signify missing/unknown ({columns_missing})")
    
    # replace all missing or unknown values column by column
    df = input_df.copy(deep=True)
    for column, missing_and_unknown_values in column_to_missing_and_unkown_values.items():
        df[column] = df[column].replace(missing_and_unknown_values, pd.NA)

    # Convert CAMEO_DEUG_2015 column to an int.  Notes on why are below.
    #
    # There are three columns that are loaded as dtype=object due to having a possible value of "X".   one column that has 
    # CAMEO_DEUG_2015: categorical, missing/unknown values = [-1,X]
    #    - Ex values: 8, 4, 2, 6, 1, 9, 5, 7, 3
    #    - Needs to be converted to an int
    # CAMEO_DEU_2015: categorical, missing/unknown values = [XX]
    #    - Ex values: 8A, 4C, 2A,
    #    - Currently is dropped rather than one-hot encoding
    # CAMEO_INTL_2015: mixed, missing/unknown values = [-1,XX]
    #    - Ex values: 51, 24, 12, 43, 54, 22, 14, 13, 15, 33
    #    - Currently is dropped rather than going through feature engineering
    df["CAMEO_DEUG_2015"] = df["CAMEO_DEUG_2015"].astype("Int64")

    return df


def get_missing_value_counts(df):
    """
    Build a dataframe that summarizes the number of NaNs in each column.

    Args:
        df: panda dataframe of the demographics data after NaNs have been
            added to replace missing/unknown data

    Return:
        df_counts: pandas dataframe summarizing NaN count by column
    """
    df_counts = pd.DataFrame(df.columns, columns=["column"])
    df_counts["count_with_vals"] = len(df) - df.isna().sum(axis=0).values
    df_counts["count_with_nans"] = len(df) - df_counts["count_with_vals"]
    df_counts["count_total"] = len(df)
    df_counts["frac_with_vals"] = df_counts["count_with_vals"] / df_counts["count_total"]
    df_counts["frac_with_nans"] = df_counts["count_with_nans"] / df_counts["count_total"]
    return df_counts


def get_nan_correlation_df(df):
    """
    Generate a correlation matrix for the presence of NaNs in data dropping all columns that
    have zero NaN.

    Args:
        df: panda dataframe of the demographics data after NaNs have been
            added to replace missing/unknown data

    Return:
        df_nan_corr: pandas dataframe giving the correlation between NaN values for columns
    """
    df_counts = get_missing_value_counts(df)
    columns_with_zero_nan = df_counts[df_counts["count_with_nans"] == 0]["column"].values

    df_nan = df.isna()
    df_nan.drop(columns=columns_with_zero_nan, inplace=True)
    df_nan_corr = df_nan.corr()

    return df_nan_corr


def get_categorical_comparison_df(df1, df2, column_name, label1="keeping", label2="dropping"):
    """
    Build a data frame that concatenate dataframes df1 and df2 and has two columns: column_name
    (provided by user) and "category", which is given a value of label1 for df1 and label2 for df2.

    Args:
        df1: pandas dataframe - demographics data
        df2: pandas dataframe - demographics data
        column_name: 
        label1: "category" for df1 points
        label2: "category" for df2 points

    Return:
        df: concatenated pandas dataframes with two columns: column_name and "category"
    """
    df1_counts = pd.DataFrame(df1[column_name].value_counts(normalize=True, dropna=True)).reset_index()
    df1_counts["category"] = label1
    df2_counts = pd.DataFrame(df2[column_name].value_counts(normalize=True, dropna=True)).reset_index()
    df2_counts["category"] = label2
    df = pd.concat([df1_counts, df2_counts]).reset_index(drop=True)
    return df


def get_unique_values_df(df, column_to_data_type):
    """
    Build dataframe that summarizes the data type (data_type), number of unique
    values (num_unique_values), and provides a string list of the ten example 
    unique values (ten_example_values) for each column in df.

    Args:
        df: pandas dataframe - demographics data
        column_to_data_type: mapping dictionary from column name to data_type
                Ex: key = "KBA13_ANZAHL_PKW", value = "numeric"

    Return:
        df_unique_values: pandas data frame with columns: "column", "data_type", 
                "num_unique_values", "ten_example_values"
    """
    data = []
    for column in df.columns:
        unique_values = df[column].dropna().unique()
        ten_example_values_str = ", ".join([str(val) for val in list(unique_values)[:10]])
        row = [column, column_to_data_type[column], len(unique_values), ten_example_values_str]
        data.append(row)
    column_names = ["column", "data_type", "num_unique_values", "ten_example_values"]
    df_unique_values = pd.DataFrame(data, columns=column_names)
    return df_unique_values


def get_praegende_jugendjahre_features(value):
    """
    Given a value for the "PRAEGENDE_JUGENDJAHRE" column, return two new categorical
    values (avantgarde and decade).

    Args:
        value: Ex: 3

    Return:
        avantgarde: dominating movement of a person's youth (0 = avantgarde, 1 = mainstream)
        decade: decade of person's youth (0 = 40s, 1 = 50s, .., 5 = 90s)
            Ex: 0, 1
    """
    ### 1.18. PRAEGENDE_JUGENDJAHRE
    # Dominating movement of person's youth (avantgarde vs. mainstream; east vs. west)
    # - -1: unknown
    # -  0: unknown
    # -  1: 40s - war years (Mainstream, E+W)
    # -  2: 40s - reconstruction years (Avantgarde, E+W)
    # -  3: 50s - economic miracle (Mainstream, E+W)
    # -  4: 50s - milk bar / Individualisation (Avantgarde, E+W)
    # -  5: 60s - economic miracle (Mainstream, E+W)
    # -  6: 60s - generation 68 / student protestors (Avantgarde, W)
    # -  7: 60s - opponents to the building of the Wall (Avantgarde, E)
    # -  8: 70s - family orientation (Mainstream, E+W)
    # -  9: 70s - peace movement (Avantgarde, E+W)
    # - 10: 80s - Generation Golf (Mainstream, W)
    # - 11: 80s - ecological awareness (Avantgarde, W)
    # - 12: 80s - FDJ / communist party youth organisation (Mainstream, E)
    # - 13: 80s - Swords into ploughshares (Avantgarde, E)
    # - 14: 90s - digital media kids (Mainstream, E+W)
    # - 15: 90s - ecological awareness (Avantgarde, E+W)
    if pd.isna(value):
        return pd.NA, pd.NA
    if not (1 <= value <= 15):
        raise ValueError(f"value ({value}) must be >= 1 and <= 15")
    avantgarde = 0 if value in (2, 4, 6, 7, 9, 11, 13, 15) else 1
    decade = None
    if value in (1, 2):
        decade = 0
    elif value in (3, 4):
        decade = 1
    elif value in (5, 6, 7):
        decade = 2
    elif value in (8, 9):
        decade = 3
    elif value in (10, 11, 12, 13):
        decade = 4
    elif  value in (14, 15):
        decade = 5

    return avantgarde, decade


def get_cameo_intl_2015_features(value):
    """
    Given a value for the "CAMEO_INTL_2015" column, return two new categorical
    values (wealth_category, life_stage_category).

    Args:
        value: Ex: 13

    Return:
        wealth_category: 
            1 = wealthy, 2 = prosperous, 3 = comfortable, 4 = less affluent, 5 = poorer
        life_stage_category:
            1 = Pre-Family Couples & Singles
            2 = Young Couples With Children
            3 = Families With School Age Children
            4 = Older Families &  Mature Couples
            5 = Elders In Retirement
    """
    ### 4.3. CAMEO_INTL_2015
    # German CAMEO: Wealth / Life Stage Typology, mapped to international code
    # - -1: unknown
    # - 11: Wealthy Households - Pre-Family Couples & Singles
    # - 12: Wealthy Households - Young Couples With Children
    # - 13: Wealthy Households - Families With School Age Children
    # - 14: Wealthy Households - Older Families &  Mature Couples
    # - 15: Wealthy Households - Elders In Retirement
    # - 21: Prosperous Households - Pre-Family Couples & Singles
    # - 22: Prosperous Households - Young Couples With Children
    # - 23: Prosperous Households - Families With School Age Children
    # - 24: Prosperous Households - Older Families & Mature Couples
    # - 25: Prosperous Households - Elders In Retirement
    # - 31: Comfortable Households - Pre-Family Couples & Singles
    # - 32: Comfortable Households - Young Couples With Children
    # - 33: Comfortable Households - Families With School Age Children
    # - 34: Comfortable Households - Older Families & Mature Couples
    # - 35: Comfortable Households - Elders In Retirement
    # - 41: Less Affluent Households - Pre-Family Couples & Singles
    # - 42: Less Affluent Households - Young Couples With Children
    # - 43: Less Affluent Households - Families With School Age Children
    # - 44: Less Affluent Households - Older Families & Mature Couples
    # - 45: Less Affluent Households - Elders In Retirement
    # - 51: Poorer Households - Pre-Family Couples & Singles
    # - 52: Poorer Households - Young Couples With Children
    # - 53: Poorer Households - Families With School Age Children
    # - 54: Poorer Households - Older Families & Mature Couples
    # - 55: Poorer Households - Elders In Retirement
    # - XX: unknown
    if pd.isna(value):
        return pd.NA, pd.NA
    value = int(value)
    if not (11 <= value <= 55):
        raise ValueError(f"value ({value}) must be >= 11 and <= 55")
    wealth_category = int(value / 10)
    life_stage_category = value // 10
    if wealth_category not in (1, 2, 3, 4, 5):
        raise ValueError(f"wealth category ({wealth_category}) must be in the range [1, 5]")
    if life_stage_category not in (1, 2, 3, 4, 5):
        raise ValueError(f"life stage category ({life_stage_category}) must be in the range [1, 5]")
    return wealth_category, life_stage_category


def check_cleaned_df(df):
    """
    Check that the final cleaned df is fit for purpose
        - All numeric, interval, and ordinal type columns from the original dataset.
        - Binary categorical features (all numerically-encoded).
        - Engineered features from other multi-level categorical features and mixed features.

    Args:
        df: pandas dataframe after all cleaning steps have been performed on demographics data
    
    Return:
        True if all checks pass, throws an exception otherwise
    """
    num_columns_in_original_dataset = 85
    column_dropped_to_num_replacements = {
            "TITEL_KZ" : 0, # not enough data
            "AGER_TYP" : 0, 
            "KK_KUNDENTYP" : 0, 
            "KBA05_BAUMAX" : 0, 
            "GEBURTSJAHR" : 0, 
            "ALTER_HH" : 0,
            "CAMEO_DEU_2015" : 0, # too many categories
            "GFK_URLAUBERTYP" : 12, # categorical that has been one hot encoded
            'LP_FAMILIE_FEIN' : 11, 
            'LP_STATUS_FEIN' : 10, 
            'CAMEO_DEUG_2015' : 9,
            'GEBAEUDETYP' : 4, 
            'CJT_GESAMTTYP' : 6, 
            'FINANZTYP' : 6, 
            'ZABEOTYP' : 6, 
            'LP_FAMILIE_GROB' : 5, 
            'LP_STATUS_GROB' : 5, 
            'SHOPPER_TYP' : 4, 
            'NATIONALITAET_KZ' : 3,
            "PRAEGENDE_JUGENDJAHRE" : 7, # mixed that has been one hot encoded
            "CAMEO_INTL_2015" : 10,
            "LP_LEBENSPHASE_FEIN" : 0, # mixed that has been dropped rather than reengineered
            "LP_LEBENSPHASE_GROB" : 0, 
            "WOHNLAGE" : 0, 
            "PLZ8_BAUMAX" : 0
            }

    # verify that the total number of columns matches what is expected
    expected_columns = num_columns_in_original_dataset - len(column_dropped_to_num_replacements)
    for num_replacements in column_dropped_to_num_replacements.values():
        expected_columns += num_replacements
    num_rows, num_columns = df.shape
    if num_columns != expected_columns:
        raise AssertionError(f"num_columns ({num_columns}) != expected_columns ({expected_columns})")

    # verify that columns expected to be dropped have been
    expected_dropped_columns = {column for column in column_dropped_to_num_replacements}
    columns = set(df.columns.tolist())
    columns_that_should_not_exist = expected_dropped_columns & columns
    if columns_that_should_not_exist != set():
        raise AssertionError(f"columns_that_should_not_exist: {columns_that_should_not_exist}")

    # verify that no rows have more than cutoff NaNs
    cutoff = 0
    for _, row in df.iterrows():
        na_count = row.isna().sum()
        if na_count > cutoff:
            raise AssertionError(f"No row should have more than {cutoff} NaNs, but a row was found with ({na_count}).")

    # verify that all (non-NaN) data is numeric (int or float)
    for column in df.columns:
        for unique_val in df[column].dropna().unique().tolist():
            if type(unique_val) not in (int, float):
                raise AssertionError(f"All (non-NaN) values are expected to be numeric (type int or float), but a value of type '{type(unique_val)}' was encountered for column '{column}'")
    return True


def one_hot_encode_column(df_input, column, unique_vals):
    """
    Perform one-hot encoding for categorical column "column" in dataframe "df_input" with unique
    values for the column given by unique_vals.

    NOTE: if there is a NaN value in df[column], it will remain a NaN in df[new_column].  This is different
              behavior from pandas get_dummies, but is the desired behavior for this function

    Args:
        df_input: pandas dataframe - demographics data
        column:
        unique_vals: list of unique values in the column.

    Return:
        df: new dataframe with one-hot encoded columns added and original column dropped.  The new
            columns are named "{column}_{unique_val}" and added in the order of unique values in
            unique_vals
    """
    # verify that there are no non-NaN values in df_input aside from those in unique_vals
    unique_vals_set = set(unique_vals)
    calculated_unique_vals_set = set(df_input[column].dropna().unique().tolist())
    unexpected_vals = calculated_unique_vals_set - unique_vals_set
    if unexpected_vals != set():
        raise ValueError(f"There are values in df_input that are not listed in the provided unique_vals. ({unexpected_vals})")
    
    # one hot encode each unique value one at a time
    df = df_input.copy()
    for unique_val in unique_vals:
        new_column = f"{column}_{unique_val}"
        # NOTE: if there is a NaN value in df[column], it will remain a NaN in df[new_column].  This is different
        #       behavior from pandas get_dummies, but is the desired behavior for this function
        df[new_column] = (df[column] == unique_val).astype("int64")

    # drop the original column after completing the one-hot encoding
    df = df.drop(columns=[column])
    return df


def modify_categorical_columns(df):
    """
    Perform cleaning steps for all categorical columns of dataframe df.

    Args:
        df: input dataframe with demographics data

    Return:
        df: dataframe with all remaining categorical columns in a format suitable
            for downstream analysis
    """
    # drop column "CAMEO_DEU_2015"
    df = df.drop(columns=["CAMEO_DEU_2015"])

    # modify column "OST_WEST_KZ" to be numerical
    df["OST_WEST_KZ"] = df["OST_WEST_KZ"].apply(lambda val: 0 if val == "W" else 1)

    # carry out one hot encoding on columns
    columns_for_one_hot_encoding = {
            'CAMEO_DEUG_2015' : [1, 2, 3, 4, 5, 6, 7, 8, 9],
            'CJT_GESAMTTYP' : [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            'FINANZTYP' : [1, 2, 3, 4, 5, 6],
            'GEBAEUDETYP' : [1.0, 3.0, 5.0, 8.0],
            "GFK_URLAUBERTYP" : [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0],
            'LP_FAMILIE_FEIN' : [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
            'LP_FAMILIE_GROB' : [1.0, 2.0, 3.0, 4.0, 5.0],
            'LP_STATUS_FEIN' : [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            'LP_STATUS_GROB' : [1.0, 2.0, 3.0, 4.0, 5.0],
            'NATIONALITAET_KZ' : [1, 2, 3],
            'SHOPPER_TYP' : [0, 1, 2, 3],
            'ZABEOTYP' : [1, 2, 3, 4, 5, 6]}
    for column, unique_vals in columns_for_one_hot_encoding.items():
        df = one_hot_encode_column(df, column, unique_vals)

    return df


def modify_mixed_type_columns(df):
    """
    Perform cleaning steps for all mixed data type columns of dataframe df.

    Args:
        df: input dataframe with demographics data

    Return:
        df: dataframe with all remaining mixed type columns in a format suitable
            for downstream analysis
    """
    # Replace "PRAEGENDE_JUGENDJAHRE" with two new categorical columns: avantgarde and decade.  Drop the
    # original column.

    # add avantgarde column
    func = lambda val: get_praegende_jugendjahre_features(val)[0]
    df["avantgarde"] = df["PRAEGENDE_JUGENDJAHRE"].apply(func)

    # add decade column
    func = lambda val: get_praegende_jugendjahre_features(val)[1]
    df["decade"] = df["PRAEGENDE_JUGENDJAHRE"].apply(func)

    # drop original column
    df = df.drop(columns=["PRAEGENDE_JUGENDJAHRE"])

    # Replace "CAMEO_INTL_2015" with two new categorical columns: wealth_category and life_stage_category.  Drop the
    # original column.  

    # add wealth_category
    func = lambda val: get_cameo_intl_2015_features(val)[0]
    df["wealth_category"] = df["CAMEO_INTL_2015"].apply(func)

    func = lambda val: get_cameo_intl_2015_features(val)[1]
    df["life_stage_category"] = df["CAMEO_INTL_2015"].apply(func)

    # drop original column
    df = df.drop(columns=["CAMEO_INTL_2015"])

    # Perform one hot encoding for any new categorical columns that need it
    columns_for_one_hot_encoding = {
            "decade" : [0, 1, 2, 3, 4, 5],
            "wealth_category" : [1, 2, 3, 4, 5],
            "life_stage_category" : [1, 2, 3, 4, 5]}
    for column, unique_vals in columns_for_one_hot_encoding.items():
        df = one_hot_encode_column(df, column, unique_vals)

    # Drop the remaining mixed data type columns
    columns_to_drop = ["LP_LEBENSPHASE_FEIN", "LP_LEBENSPHASE_GROB", "WOHNLAGE", "PLZ8_BAUMAX"]
    df = df.drop(columns=columns_to_drop)

    return df


def clean_data(df_demographics, df_feature_summary, cutoff=0):
    """
    Perform all steps required to clean the raw df_demographics dataframe.

    Args:
        df_demographics: pandas dataframe loaded from Udacity_AZDIAS_Subset.csv
        df_feature_summary: pandas dataframe loaded from AZDIAS_Feature_Summary.csv
        cutoff: keep rows that have <= cutoff NaNs
    """
    # build a helper dictionary that maps from column name to a list of values (of
    # the correct type) that are missing or unknown for that column
    column_to_missing_and_unkown_values = build_column_to_missing_and_unkown_values(df_feature_summary)

    # Identify missing or unknown data values and convert them to NaNs.
    df = set_missing_and_unknown_to_nan(df_demographics, column_to_missing_and_unkown_values)

    # Remove the outlier columns from the dataset
    outlier_columns = ["TITEL_KZ", "AGER_TYP", "KK_KUNDENTYP", "KBA05_BAUMAX", "GEBURTSJAHR", "ALTER_HH"]
    df = df.drop(columns=outlier_columns)

    # Drop rows with > cutoff NaN values
    nan_count_by_row = df.isna().sum(axis=1).values
    df = df.iloc[nan_count_by_row<=cutoff]

    # Re-encode categorical variable(s) to be kept in the analysis.
    df = modify_categorical_columns(df)
    
    # Modify mixed variables to be kept in the analysis
    df = modify_mixed_type_columns(df)

    return df


def get_pca_components_df(pca, column_names):
    """
    Build a dataframe that summarizes PCA eigenvectors in a dataframe with "column_name"
    and "column_num" columns added.

    Args:
        pca: sklearn.decomposition.PCA object after it has been fit (and pca.explained_variance_ratio_
             has been set)
        column_names: list of all feature names with which to annotate pca eigenvectors in the
                "column_name" column

    Return:
        df: pandas dataframe with columns "column_name", "column_num", 
            "0", "1", .., "<num_pca_components>"
    """
    num_components, num_columns = pca.components_.shape
    num_components = len(pca.components_)
    if len(column_names) != num_columns:
        raise ValueError(f"length of column_names ({len(column_names)}) does not match pca.components_ ({num_columns})")
    df = pd.DataFrame(pca.components_.T, columns=[i for i in range(num_components)])
    df.insert(loc=0, column="column_name", value=column_names)
    df.insert(loc=1, column="column_num", value=[i for i in range(num_columns)])

    return df


def get_cluster_counts_df(cluster_labels_arr, unique_cluster_ids_sorted):
    """
    Build a dataframe summarizing cluster counts.

    Args:
        cluster_labels_arr: np.array output from kmeans.predict(data_pca)
        unique_cluster_ids_sorted: sorted list of all unique cluster IDs.
                NOTE: this is a parameter to ensure that when you apply this function on
                non-general population data, which may have some clusters with a count of
                zero, that these still appear in the final data frame with a count of zero

    Return:
        df: pandas dataframe summarizing count info for each cluster.
            Columns:
                cluster_id: cluster label from cluster_labels_arr
                count: number in cluster
                count_error: error in count (sqrt(count))
                frac: proportion of total count in cluster (count_cluster / count_total)
                frac_error: count_error / count_total
    """
    counter = collections.Counter(cluster_labels_arr)
    total_count = len(cluster_labels_arr)
    cluster_ids = list(counter.keys())
    cluster_ids.sort()
    data = []
    for cluster_id in unique_cluster_ids_sorted:
        count = counter[cluster_id]
        count_error = np.sqrt(count)
        frac = count / total_count
        # TODO: this way of calculating frac_error is not quite right. I should use
        #       full error propagation as done in normalize_cluster_comparison_df().  
        #       However, since this will have a small impact on the final result, I 
        #       will leave this for a future improvement.
        frac_error = count_error / total_count
        row = [cluster_id, count, count_error, frac, frac_error]
        data.append(row)
    df = pd.DataFrame(data, columns=["cluster_id", "count", "count_error", "frac", "frac_error"])

    # checks on the final data frame
    if df["count"].sum() != len(cluster_labels_arr):
        raise AssertionError(f"the sum of the 'count' column ({total_count}) does not match the length of cluster_labels_arr ({len(cluster_labels_arr)})")

    frac_column_sum = df["frac"].sum()
    if frac_column_sum != 1.0:
        raise AssertionError(f"the 'frac' column sums to {frac_column_sum}, not 1.0")
    
    return df


def normalize_cluster_comparison_df(df, normalization_basis_group):
    """
    Add two in columns (normalized_frac, normalized_frac_error) to df (in place) 
    normalizing cluster counts by df["group"] == normalization_basis_group.  This 
    is used to normalize customer cluster fracs by general population cluster fracs.

    Args:
        df: concatenated dataframes generated using get_cluster_counts_df() and with
            a new "group" column added
        normalization_basis_group: group to use as the basis for normalization.

    Return:
        None
    """
    # build helper dictionary
    cluster_id_to_frac_for_normalization = dict()
    cluster_id_to_frac_error_for_normalization = dict()
    for _, row in df[df["group"] == normalization_basis_group].iterrows():
        cluster_id = row["cluster_id"]
        frac = row["frac"]
        frac_error = row["frac_error"]
        if frac == 0:
            raise ValueError(f"fraction to which to normalize ({frac}) is zero, which will result in divide by zero errors during normalization")
        if cluster_id in cluster_id_to_frac_for_normalization:
            raise AssertionError(f"cluster_id ({cluster_id}) is repeated")
        cluster_id_to_frac_for_normalization[cluster_id] = frac
        cluster_id_to_frac_error_for_normalization[cluster_id] = frac_error
    
    # build normalization data
    normalized_fracs = []
    normalized_frac_errors = []
    for _, row in df.iterrows():
        cluster_id = row["cluster_id"]
        frac = row["frac"]
        frac_error = row["frac_error"]

        if cluster_id not in cluster_id_to_frac_for_normalization:
            raise ValueError(f"cluster_id ({cluster_id}) was not found in the '{normalization_basis_group}' group used for normalization")

        # NOTE: propogated error for normalized_frac_error is given below and follows the standard
        #       multi-variate process.
        #       x := frac
        #       y := frac_for_normalization
        #       q := normalized_frac
        #       q = x / y
        #       dx := error in x (frac_error)
        #       dy := error in y (frac_error_for_normalization)
        #       dq := error in q (normalized_frac_error)
        #       dq = sqrt( (dx / y)^2 + ((x*dy)/y^2)^2 )
        x = frac
        y = cluster_id_to_frac_for_normalization[cluster_id]
        q = x / y
        dx = frac_error
        dy = cluster_id_to_frac_error_for_normalization[cluster_id]
        dq = np.sqrt((dx/y)**2 + (x*dy/y**2)**2)

        normalized_frac = q
        normalized_frac_error = dq

        normalized_fracs.append(normalized_frac)
        normalized_frac_errors.append(normalized_frac_error)

    # add a new column with the normalized fraction
    df["normalized_frac"] = normalized_fracs
    df["normalized_frac_error"] = normalized_frac_errors

    return


def get_cluster_counts_comparison_df(cluster_labels_1, cluster_labels_2, groups, normalization_basis_group):
    """
    Generate two dataframes summarizing the counts, proportions, and relative proportions for
    people in each cluster.  The two dataframes generated have identical data, but are provided
    in a "wide" format (easier for reading through the data visually) and a "long" format (easier
    for downstream data analysis and plotting).

    Args:
        cluster_labels_1: np.array output from kmeans.predict(data_pca) for group 1
        cluster_labels_2: np.array output from kmeans.predict(data_pca) for group 2
        groups: list of length two with string label cluster_labels_1 and cluster_labels_2 data
        normalization_basis_group: group (must be in groups) to use as basis for normalization

    Return:
        df_wide:
            Columns:
                cluster_id
                count
                count_error
                frac
                frac_error
                group
                normalized_frac
                normalized_frac_error
        df_long:
            Columns:
                cluster_id
                [count][cluster_labels_1/cluster_labels_2]
                [count_error][cluster_labels_1/cluster_labels_2]
                [frac][cluster_labels_1/cluster_labels_2]
                [frac_error][cluster_labels_1/cluster_labels_2]
                [normalized_frac][cluster_labels_1/cluster_labels_2]
                [normalized_frac_error][cluster_labels_1/cluster_labels_2]
    """
    if len(groups) != 2:
        raise ValueError(f"groups must contain two group names, but it contains ({len(groups)})")
    if normalization_basis_group not in groups:
        raise ValueError(f"the normalization_basis_group ({normalization_basis_group}) must be in groups ({groups})")

    unique_cluster_ids_sorted = list(set(cluster_labels_1) | set(cluster_labels_2))
    unique_cluster_ids_sorted.sort()

    # load group 1
    df_cluster_counts_1 = get_cluster_counts_df(cluster_labels_1, unique_cluster_ids_sorted)
    df_cluster_counts_1["group"] = groups[0]
    
    # load group 2
    df_cluster_counts_2 = get_cluster_counts_df(cluster_labels_2, unique_cluster_ids_sorted)
    df_cluster_counts_2["group"] = groups[1]

    # concat group 2 to group 1 to create the "long" dataframe (easier for data manipulation)
    df_cluster_comparison_long = pd.concat([df_cluster_counts_1, df_cluster_counts_2]).reset_index(drop=True)

    # normalize all frac data to normalize_group name
    normalize_cluster_comparison_df(df_cluster_comparison_long, normalization_basis_group)

    # pivot the dataframe to create the "wide" dataframe (easier for reading)
    values_list = ["count", "count_error", "frac", "frac_error", "normalized_frac", "normalized_frac_error"]
    df_cluster_comparison_wide = \
            df_cluster_comparison_long.pivot(index=["cluster_id"], columns=["group"], values=values_list)
    df_cluster_comparison_wide["count"] = df_cluster_comparison_wide["count"].fillna(0).astype(int)

    return df_cluster_comparison_wide, df_cluster_comparison_long


def get_centroids(kmeans, pca, scaler):
    """
    Return the centroids from kmeans clustering in all coordinate systems.

    Args:
        kmeans: sklearn.cluster.KMeans object that was used to cluster the data
        pca: sklearn.decomposition.PCA object that was used to fit the data
        scaler: sklearn.preprocessing.StandardScaler object that was used to scale
                the cleaned data
    
    Return:
        centroids_pca: centroids in PCA coordinates, np.array, shape = (num_clusters, num_pca)
        centroids_scaled: centroids in scaled coordinates, np.array, shape = (num_clusters, num_features)
        centroids_unscaled: centroids in unscaled coordinates, np.array, shape = (num_clusters, num_features)
    """
    centroids_pca = kmeans.cluster_centers_.copy()
    centroids_scaled = pca.inverse_transform(centroids_pca)
    centroids_unscaled = scaler.inverse_transform(centroids_scaled)
    return centroids_pca, centroids_scaled, centroids_unscaled


def build_centroids_df(centroids, feature_names, df_cluster_comparison_long):
    """
    Build a dataframe with several columns prepended to the centroid coordinates (cluster_id,
    normalized_customer_frac, and demographics_frac).

    Args:
        centroids: centroid coordinates, np.array, shape = (num_clusters, num_features)
        feature_names: list of feature names for each column of centroids
        df_cluster_comparison_long: pandas dataframe with cluster comparison information generated
                by get_cluster_counts_comparison_df()

    Return:
        df: pandas dataframe with the centroid coordinates and prepended columns: cluster_id,
                normalized_customer_frac, and demographics_frac
    """
    columns = ["cluster_id", "normalized_customer_frac", "demographics_frac"] + feature_names
    num_centroids, num_features = centroids.shape
    
    # add cluster_ids column
    cluster_ids = np.arange(num_centroids)
    data = np.insert(centroids, 0, cluster_ids, axis=1)

    # add normalized_customer_frac column
    idx = (df_cluster_comparison_long["group"] == "customer")
    normalized_customer_frac = df_cluster_comparison_long[idx]["normalized_frac"]
    data = np.insert(data, 1, normalized_customer_frac, axis=1)

    # add demographics_frac column
    idx = (df_cluster_comparison_long["group"] == "demographics")
    demographics_frac = df_cluster_comparison_long[idx]["frac"]
    data = np.insert(data, 2, demographics_frac, axis=1)
    
    # build data frame
    df = pd.DataFrame(data, columns=columns)
    df["cluster_id"] = df["cluster_id"].astype(int)

    # sort by "normalized_customer_frac"
    df.sort_values(by="normalized_customer_frac", inplace=True)
    return df


def get_centroids_df(kmeans, pca, scaler, df_cluster_comparison_long):
    """
    Build a dataframe with several columns prepended to the centroid coordinates (cluster_id,
    normalized_customer_frac, and demographics_frac) for each coordinate system (PCA, scaled,
    and unscaled)

    Args:

    Return:
        (format of dataframes is described in build_centroids_df())
        df_centroids_pca: pandas dataframe for centroid PCA coordinates
        df_centroids_scaled: pandas dataframe for centroid scaled coordinates
        df_centroids_unscaled: pandas dataframe for centroid unscaled coordinates
    """
    centroids_pca, centroids_scaled, centroids_unscaled = get_centroids(kmeans, pca, scaler)

    pca_feature_names = [f"pca_{i}" for i in range(len(scaler.feature_names_in_))]
    df_centroids_pca = build_centroids_df(centroids_pca, pca_feature_names, df_cluster_comparison_long)
    
    scaled_feature_names = [f"scaled_{feature}" for feature in scaler.feature_names_in_]
    df_centroids_scaled = build_centroids_df(centroids_scaled, scaled_feature_names, df_cluster_comparison_long)

    unscaled_feature_names = list(scaler.feature_names_in_)
    df_centroids_unscaled = build_centroids_df(centroids_unscaled, unscaled_feature_names, df_cluster_comparison_long)

    return df_centroids_pca, df_centroids_scaled, df_centroids_unscaled