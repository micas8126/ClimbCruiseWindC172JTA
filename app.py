import pandas as pd
import numpy as np
import streamlit as st
import math

# Daten laden
cruise_df = pd.read_csv("cruise_performance_combined.csv")
climb_df = pd.read_csv("climb_performance_verified.csv")

# UI
st.title("Reisezeit- & Verbrauchsrechner: Climb + Cruise")
st.markdown("Berechnung von **Time** und **Fuel [l]** unter Berücksichtigung von Steigflug, Reiseflug, Alternate, Reserve und Wind")

# Eingaben
weight_input = st.number_input("Gewicht [kg]", min_value=1111, max_value=1157, step=1)
total_distance = st.number_input("Gesamtdistanz [NM]", min_value=10.0, step=1.0)
start_altitude = st.number_input("Startflughöhe [ft]", min_value=0, max_value=18000, step=100)
target_altitude = st.number_input("Ziel-Flughöhe [ft]", min_value=0, max_value=18000, step=100)
load_input = st.selectbox("Cruise Load [%]", sorted(cruise_df["Load [%]"].unique(), reverse=True))
alternate_distance = st.number_input("Alternate-Distanz [NM]", min_value=0.0, step=1.0)
additional_fuel = st.number_input("Zusätzlicher Kraftstoff [l]", min_value=0.0, step=0.5)

# Wind-Eingaben
st.markdown("---")
st.subheader("Winddaten")
track = st.number_input("Flugrichtung (Track) [°]", min_value=0, max_value=360, step=1)
wind_dir = st.number_input("Windrichtung (woher) [°]", min_value=0, max_value=360, step=1)
wind_speed = st.number_input("Windstärke [kt]", min_value=0.0, step=0.5)

# ✅ Korrekte Windkomponentenberechnung
def calc_wind_component(wind_dir, track, wind_speed):
    wind_vector_dir = (wind_dir + 180) % 360
    angle = math.radians((wind_vector_dir - track + 180) % 360 - 180)
    return wind_speed * math.cos(angle)

wind_comp = calc_wind_component(wind_dir, track, wind_speed)

# Rundung auf nächstverfügbare Höhen
available_climb_altitudes = sorted(climb_df["Pressure Altitude [ft]"].unique())
available_cruise_altitudes = sorted(cruise_df["Pressure Altitude [ft]"].unique())

raw_climb_altitude = target_altitude - start_altitude
climb_altitude = min([alt for alt in available_climb_altitudes if alt >= raw_climb_altitude], default=None)
rounded_target_altitude = min([alt for alt in available_cruise_altitudes if alt >= target_altitude], default=None)

# Anzeige der gerundeten Werte
st.markdown(f"**Gerundete Climb-Höhe über Startplatz:** {climb_altitude if climb_altitude is not None else 'nicht verfügbar'} ft")
st.markdown(f"**Gerundete Cruise-Höhe:** {rounded_target_altitude if rounded_target_altitude is not None else 'nicht verfügbar'} ft")

# Hilfsfunktion zur Zeitformatierung
def format_time(hours):
    h = int(hours)
    m = int(round((hours - h) * 60))
    return f"{h}:{m:02d} h"

# Initialwerte
time_alt = 0.0
fuel_alt = 0.0

# Berechnung für Alternate separat mit fixen Werten (auf 4000 ft angepasst)
alt_subset = cruise_df[(cruise_df["Pressure Altitude [ft]"] == 4000) &
                       (cruise_df["Load [%]"] == 60)]
if len(alt_subset) >= 2:
    alt_weights = alt_subset["Weight [kg]"].values
    alt_speed_tas = np.interp(1134, alt_weights, alt_subset["Speed [KTAS]"].values)
    alt_flow = np.interp(1134, alt_weights, alt_subset["Fuel Flow [l/h]"].values)
    alt_ground_speed = max(alt_speed_tas + wind_comp, 30)  # min GS-Schutz
    time_alt = alternate_distance / alt_ground_speed
    fuel_alt = time_alt * alt_flow

# Hauptflug (Climb + Cruise)
if climb_altitude is None:
    st.error("Keine passende Climb-Höhe verfügbar. Bitte niedrigere Zielhöhe eingeben.")
elif rounded_target_altitude is None:
    st.error("Keine passende Cruise-Höhe verfügbar. Bitte niedrigere Zielhöhe eingeben.")
else:
    climb_segment = climb_df[climb_df["Pressure Altitude [ft]"] == climb_altitude]

    if len(climb_segment) >= 2:
        weights = climb_segment["Weight [kg]"].values
        time_climb = np.interp(weight_input, weights, climb_segment["Time [MIN]"].values) / 60
        fuel_climb = np.interp(weight_input, weights, climb_segment["Fuel [l]"].values)
        dist_climb = np.interp(weight_input, weights, climb_segment["Distance [NM]"].values)

        remaining_distance = total_distance - dist_climb
        if remaining_distance <= 0:
            st.error("Gesamtdistanz ist kleiner als Climb-Distanz. Bitte höhere Distanz eingeben.")
        else:
            cruise_subset = cruise_df[(cruise_df["Pressure Altitude [ft]"] == rounded_target_altitude) &
                                      (cruise_df["Load [%]"] == load_input)]

            if len(cruise_subset) >= 2:
                weights = cruise_subset["Weight [kg]"].values
                speed_cruise_tas = np.interp(weight_input, weights, cruise_subset["Speed [KTAS]"].values)
                fuel_flow_cruise = np.interp(weight_input, weights, cruise_subset["Fuel Flow [l/h]"].values)
                ground_speed = max(speed_cruise_tas + wind_comp, 30)

                time_cruise = remaining_distance / ground_speed
                fuel_cruise = time_cruise * fuel_flow_cruise

                fuel_departure = 4.0  # Startfix
                fuel_landing = 1.0    # Landeanflug
                fuel_reserve = 17.0   # Reserve fix

                # ✅ Korrigierter Gesamtverbrauch (ohne Alternate)
                total_fuel = fuel_climb + fuel_cruise + fuel_departure + fuel_landing

                # ✅ Endgültige Gesamtsumme inkl. Reserve, Zusatz, Alternate
                grand_total_fuel = total_fuel + fuel_reserve + additional_fuel + fuel_alt

                st.success("Ergebnisse")

                if wind_comp < 0:
                    st.write(f"**Gegenwind:** {abs(wind_comp):.1f} kt")
                elif wind_comp > 0:
                    st.write(f"**Rückenwind:** {wind_comp:.1f} kt")
                else:
                    st.write("**Windkomponente:** 0 kt (Querwind)")

                st.write(f"**Climb {climb_altitude} ft über Startplatz:** {format_time(time_climb)}, {fuel_climb:.1f} l, {dist_climb:.1f} NM")
                st.write(f"**Cruise auf {rounded_target_altitude} ft:** {format_time(time_cruise)}, {fuel_cruise:.1f} l, {remaining_distance:.1f} NM")
                st.write("---")
                st.write(f"**Startzuschlag:** {fuel_departure:.1f} l")
                st.write(f"**Landung:** {fuel_landing:.1f} l")
                st.write(f"**Reserve:** {fuel_reserve:.1f} l")
                st.write(f"**Zusatzkraftstoff:** {additional_fuel:.1f} l")
                st.write("---")
                st.write(f"**Alternate-Flug:** {format_time(time_alt)}, {fuel_alt:.1f} l")
                st.write(f"**Gesamtdauer (ohne Alternate):** {format_time(time_climb + time_cruise)}")
                st.write(f"**Gesamtverbrauch (ohne Alternate):** {total_fuel:.1f} Liter")
                st.write(f"**Gesamtverbrauch inkl. Alternate:** {grand_total_fuel:.1f} Liter")
            else:
                st.warning("Nicht genug Daten für Cruise-Interpolation.")
    else:
        st.warning("Keine passenden Climb-Daten gefunden für die berechnete Climb-Höhe.")
