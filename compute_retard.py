import pandas as pd
from datetime import datetime




def compute_retards(df_prevu, df_reel, date_str):
    """
    Calcule les retards entre df_prevu (J-1) et df_reel (J-1),
    et conserve les colonnes Statut + Modes provenant du réel.
    date_str = 'YYYY-MM-DD'
    """

    # Renommer les colonnes pour distinguer prévu / réel 
    df_prev = df_prevu.rename(columns={
        "Depart": "Depart_prevu",
        "Arrivee": "Arrivee_prevu",
        "Duree(min)": "Duree_prev"
    })

    df_rel = df_reel.rename(columns={
        "Depart": "Depart_reel",
        "Arrivee": "Arrivee_reel",
        "Duree(min)": "Duree_reel"
    })
    
    # Conserver Statut & Modes du RÉEL 
    df_prev = df_prev.drop(columns=["Modes", "Statut"], errors="ignore")

    # Merge sur Train 
    df = df_rel.merge(df_prev, on="Train", how="left")

    # Construire datetime 
    def to_dt(series):
        return pd.to_datetime(
            date_str + " " + series.astype(str),
            format="%Y-%m-%d %H:%M",
            errors="coerce"
        )

    df["Depart_prevu_dt"]  = to_dt(df["Depart_prevu"])
    df["Depart_reel_dt"]   = to_dt(df["Depart_reel"])
    df["Arrivee_prevu_dt"] = to_dt(df["Arrivee_prevu"])
    df["Arrivee_reel_dt"]  = to_dt(df["Arrivee_reel"])

    # Calcul des retards 
    df["Retard_depart(min)"]  = (df["Depart_reel_dt"]  - df["Depart_prevu_dt"]).dt.total_seconds() / 60
    df["Retard_arrivee(min)"] = (df["Arrivee_reel_dt"] - df["Arrivee_prevu_dt"]).dt.total_seconds() / 60
    df["Retard_duree(min)"]   = df["Duree_reel"] - df["Duree_prev"]
    
    # Retour final (propre et trié) 
    return df[[
        "Train",

        # Horaires et retards
        "Depart_prevu", "Depart_reel", "Retard_depart(min)",
        "Arrivee_prevu", "Arrivee_reel", "Retard_arrivee(min)",

        # Durées
        "Duree_prev", "Duree_reel", "Retard_duree(min)",

        # Infos du réel
        "Modes", "Statut"
    ]]

    