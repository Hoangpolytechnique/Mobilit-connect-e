import os
import io
from datetime import datetime, timedelta
import pandas as pd
from sncf_api import fetch_tgv_data_routes
from compute_retard import compute_retards
import boto3

# Env variables
S3_BUCKET = "sncf-delays-data"
S3_PREFIX = "sncf-retards/"

CAMPAIGN_START = "2025-11-27"
CAMPAIGN_END   = "2026-01-27"

# ROUTES defined here for simplicity (stop_area ids)
ROUTES = [
("ParisMontparnasse_Bordeaux", "stop_area:SNCF:87391003", "stop_area:SNCF:87581009"),
("ParisMontparnasse_Rennes", "stop_area:SNCF:87391003", "stop_area:SNCF:87471003"),
("ParisMontparnasse_Nantes", "stop_area:SNCF:87391003", "stop_area:SNCF:87481002"),
("ParisMontparnasse_Toulouse", "stop_area:SNCF:87391003", "stop_area:SNCF:87611004"),
("ParisGareDuNord_Lille", "stop_area:SNCF:87271007", "stop_area:SNCF:87286005"),
("ParisEst_Strasbourg", "stop_area:SNCF:87113001", "stop_area:SNCF:87212027"),
("ParisGareDeLyon_LyonPartDieu","stop_area:SNCF:87686006", "stop_area:SNCF:87723197"),
("ParisGareDeLyon_Marseille", "stop_area:SNCF:87686006", "stop_area:SNCF:87751008"),
("ParisGareDeLyon_Montpellier_centre", "stop_area:SNCF:87686006", "stop_area:SNCF:87773002"),
("ParisGareDeLyon_Montpellier_sud", "stop_area:SNCF:87686006", "stop_area:SNCF:87688887"),
("ParisGareDeLyon_Grenoble", "stop_area:SNCF:87686006", "stop_area:SNCF:87747006"),
("ParisGareDeLyon_Belfort", "stop_area:SNCF:87686006", "stop_area:SNCF:87300822"),
]




def upload_df_to_s3(df, bucket, key):
    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=key, Body=df.to_csv(index=False).encode("utf-8"))
    print(f"Uploaded: s3://{bucket}/{key}")
    
def download_df_from_s3(bucket, key):
    s3 = boto3.client("s3")
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        return pd.read_csv(io.BytesIO(resp['Body'].read()))
    except Exception as e:
        print(f"[S3] Impossible de charger {key} : {e}")
        return pd.DataFrame()

def within_campaign(now):
    d = now.date()
    start = datetime.strptime(CAMPAIGN_START, "%Y-%m-%d").date()
    end = datetime.strptime(CAMPAIGN_END, "%Y-%m-%d").date()
    return start <= d <= end


def lambda_handler(event, context):

    now = datetime.now()

    # Exécute seulement entre le 27/11 et le 17/01
    if not within_campaign(now):
        return {"status": "outside campaign period"}

    # Format pour recherche SNCF
    date_prev = now.strftime("%Y%m%d")                       # services prévus du jour
    date_reel = (now - timedelta(days=1)).strftime("%Y%m%d") # services réels du jour précédent

    # Pour dossiers S3
    date_folder = now.strftime("%Y-%m-%d")
    date_folder_reel  = (now - timedelta(days=1)).strftime("%Y-%m-%d") # réel  = hier


    for route_name, stop_from, stop_to in ROUTES:

        # SERVICES PRÉVUS (du jour même)
        try:
            df_prevu = fetch_tgv_data_routes(stop_from, stop_to, date_prev)
        except Exception as e:
            print(f"[PREVU] {route_name} erreur : {e}")
            df_prevu = pd.DataFrame()

        if not df_prevu.empty:
            key_prevu = f"{S3_PREFIX}{date_folder}/{route_name}_prevu_{date_folder}.csv"
            upload_df_to_s3(df_prevu, S3_BUCKET, key_prevu)

        # SERVICES RÉELS (du jour précédent)
        try:
            df_reel = fetch_tgv_data_routes(stop_from, stop_to, date_reel)
        except Exception as e:
            print(f"[REEL] {route_name} erreur : {e}")
            df_reel = pd.DataFrame()

        if not df_reel.empty:
            key_reel = f"{S3_PREFIX}{date_folder_reel}/{route_name}_reel_{date_folder_reel}.csv"
            upload_df_to_s3(df_reel, S3_BUCKET, key_reel)
            
        # CALCUL DES RETARDS & SAUVEGARDE 
        # essayer de charger le PREVU J-1 depuis S3 (créé la veille)
        key_prev_s3 = f"{S3_PREFIX}{date_folder_reel}/{route_name}_prevu_{date_folder_reel}.csv"
        df_prevu_hier = download_df_from_s3(S3_BUCKET, key_prev_s3)
        if df_prevu_hier.empty:
            print(f"[WARN] Pas de PREVU de Jour précédent trouvé pour {route_name} (clé: {key_prev_s3})")
        if not df_reel.empty and not df_prevu_hier.empty:
            try:
                df_retards = compute_retards(df_prevu_hier, df_reel,date_folder_reel)

                # fichier du jour J-1
                key_retards = f"{S3_PREFIX}{date_folder_reel}/retards_{route_name}_{date_folder_reel}.csv"
                upload_df_to_s3(df_retards, S3_BUCKET, key_retards)
                print(f"[RETARDS] OK {route_name} -> {key_retards}")

            except Exception as e:
                print(f"[RETARDS] Erreur pour {route_name} : {e}")
        else:
             print(f"[RETARDS] impossible {route_name}: prevu_J-1 empty={df_prevu_hier.empty}, reel_J-1 empty={df_reel.empty}")

    return {"status": "done", "date": date_folder}