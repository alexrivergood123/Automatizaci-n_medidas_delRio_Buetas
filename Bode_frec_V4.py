# -*- coding: utf-8 -*-
"""
Versión modificada - Oct 2025
@author: alexr y mbuetas
"""

import numpy as np
import matplotlib.pyplot as plt
import pyvisa
import time
start = time.time()

FREQ_INICIAL = 50
FREQ_FINAL = 50000000
NUM_PUNTOS = 500
VIN = 3
N_MEDIDAS = 3

SR_MAX = 14.5
FREQ_SR_INICIO = 2000000
VIN_MIN = 0.5
PASO_VOLT = 0.5

frecuencias = np.logspace(np.log10(FREQ_INICIAL), np.log10(FREQ_FINAL), NUM_PUNTOS)
ganancia_db = []
ganancia_err = []
fase_deg = []
fase_err = []

rm = pyvisa.ResourceManager()
print("Recursos disponibles:", rm.list_resources())

osc = rm.open_resource("visa://155.210.95.41/USB0::0x0957::0x179B::MY50512084::INSTR")
osc.write_termination = '\n'
osc.read_termination = '\n'

osc.write("WGEN:FUNC SIN")
osc.write(f"WGEN:VOLT {VIN}")
osc.write("WGEN:VOLT:OFFS 0")
osc.write("WGEN:OUTP 1")
osc.write("CHAN1:VOLT:OFFS 0")
osc.write("CHAN2:VOLT:OFFS 0")
osc.write(f"CHAN1:SCALe {VIN/3}")
osc.write(":MEAS:VPP CHAN2")
escalain = float(osc.query(":MEAS:VPP?"))
osc.write(f"CHAN2:SCALe {escalain/6}")
osc.write(f"TIM:SCAL {3/(10*FREQ_INICIAL)}")
osc.write(":ACQuire:TYPE AVER")

def ajustar_escalas_frec(f):
    time_scale = 3 / (10 * f)
    osc.write(f"TIM:SCAL {time_scale}")

def ajustar_escalas_frec_SR(f):
    time_scale = 1 / (10 * f)
    osc.write(f"TIM:SCAL {time_scale}")

def ajustar_escalas_volt(volt):
    volt_scale = volt / 3  
    osc.write(f"CHAN2:SCALe {volt_scale}")
    osc.write("CHAN2:VOLT:OFFS 0")

def medir_SR_experimental_con_vin(f, vin_local):
    osc.write("WGEN:FUNC STEP")
    osc.write(f"WGEN:VOLT {vin_local}")
    osc.write(f"WGEN:FREQ {f}")
    ajustar_escalas_frec_SR(f)
    ajustar_escalas_volt(vin_local)
    time.sleep(0.5)
    sr_values = []
    for _ in range(3):
        try:
            osc.write(":MEAS:RIS CHAN2")
            t_rise = float(osc.query(":MEAS:RIS?"))
            osc.write(":MEAS:VPP CHAN2")
            Vpp = float(osc.query(":MEAS:VPP?"))
            SR_measured = (0.8 * Vpp) / t_rise / 1e6
            sr_values.append(SR_measured)
            time.sleep(0.2)
        except pyvisa.errors.VisaIOError:
            sr_values.append(np.nan)
            time.sleep(0.1)
    osc.write("WGEN:FUNC SIN")
    osc.write(f"WGEN:FREQ {f}")
    return sr_values

def ajustar_VIN_por_SR(f, vin):
    if f < FREQ_SR_INICIO:
        return vin
    VIN_actual = vin
    while VIN_actual > VIN_MIN:
        sr_mediciones = medir_SR_experimental_con_vin(f, VIN_actual)
        cumple_todas = True
        for sr in sr_mediciones:
            if sr > SR_MAX:
                cumple_todas = False
                break
        if cumple_todas:
            return VIN_actual
        else:
            VIN_actual -= PASO_VOLT
    return VIN_MIN


for f in frecuencias:
    VIN_ajustado = ajustar_VIN_por_SR(f, VIN)
    osc.write(f"WGEN:VOLT {VIN_ajustado}")
    osc.write(f"WGEN:FREQ {f}")
    
    time.sleep(0.5 + 4/f)

    if 10*float(osc.query("TIM:SCAL?")) < 5/f:
        ajustar_escalas_frec(f)

    osc.write(":MEAS:VPP CHAN2")
    if float(osc.query(":MEAS:VPP?")) < 4*float(osc.query("CHAN2:SCALe?")) or float(osc.query(":MEAS:VPP?")) > 7*float(osc.query("CHAN2:SCALe?")):
        ajustar_escalas_volt(float(osc.query(":MEAS:VPP?"))/2)

    cocientes_locales = []
    fases_locales = []

    for i in range(N_MEDIDAS):
        try:
            osc.write(":MEAS:VPP CHAN2")
            Vout_pp = float(osc.query(":MEAS:VPP?"))
            osc.write(":MEAS:VPP CHAN1")
            Vin_pp = float(osc.query(":MEAS:VPP?"))
            cociente = Vout_pp / Vin_pp
            cocientes_locales.append(cociente)
            osc.write(":MEAS:PHAS CHAN2,CHAN1")
            fase = float(osc.query(":MEAS:PHAS?"))
            if -360 <= fase <= 360:
                fases_locales.append(fase)
            time.sleep(0.1)
        except pyvisa.errors.VisaIOError:
            print(f"Timeout a {f:.1f} Hz en medida {i+1}")
            continue

    if cocientes_locales:
        coc_mean = np.mean(cocientes_locales)
        coc_std = np.std(cocientes_locales, ddof=1)
        G_mean = 20 * np.log10(coc_mean)
        G_std = 20 / np.log(10) * (coc_std / coc_mean)
    else:
        G_mean = np.nan
        G_std = np.nan

    ganancia_db.append(G_mean)
    ganancia_err.append(G_std)

    if fases_locales:
        fase_mean = np.mean(fases_locales)
        fase_std = np.std(fases_locales, ddof=1)
    else:
        fase_mean = np.nan
        fase_std = np.nan

    fase_deg.append(fase_mean)
    fase_err.append(fase_std)
    
    print(f"{f:.2f} Hz → VIN={VIN_ajustado:.3f} Vpp | G = {G_mean:.2f} ± {G_std:.2f} dB | Fase = {fase_mean:.2f} ± {fase_std:.2f}°")

end = time.time()

with open(r"C:\Users\alexr\OneDrive\Desktop\Máster Física Y Tecnologías Físicas\Primer Cuatri\Instrumentación Inteligente\Codigo\txt\medidas_bode.txt", "w", encoding="utf-8") as file:
    file.write("Frecuencia(Hz)\tGanancia(dB)\tError_Ganancia(dB)\tFase(°)\tError_Fase(°)\n")
    for f, g, ge, ph, phe in zip(frecuencias, ganancia_db, ganancia_err, fase_deg, fase_err):
        file.write(f"{f:.6e}\t{g:.6f}\t{ge:.6f}\t{ph:.6f}\t{phe:.6f}\n")

ganancia_max = np.nanmax(ganancia_db)
ganancia_3db = ganancia_max - 3

idx_validos = np.isfinite(ganancia_db)
frecuencias_validas = frecuencias[idx_validos]
ganancias_validas = np.array(ganancia_db)[idx_validos]

idx_bw = np.where(ganancias_validas <= ganancia_3db)[0]
if len(idx_bw) > 0:
    ancho_de_banda = frecuencias_validas[idx_bw[0]]
    print(f"\nAncho de banda (−3 dB): {ancho_de_banda:.2f} Hz <<<")
else:
    ancho_de_banda = None
    print("\nBruh")

plt.figure(figsize=(10,6))
plt.errorbar(frecuencias, ganancia_db, yerr=ganancia_err, fmt='o-', capsize=4)
plt.axhline(ganancia_3db, color='r', linestyle='--', label='Nivel -3 dB')
if ancho_de_banda:
    plt.axvline(ancho_de_banda, color='g', linestyle='--', label=f'BW = {ancho_de_banda:.1f} Hz')
plt.xscale("log")
plt.grid(which='both', linestyle='--', linewidth=0.5)
plt.title("Diagrama de Bode - Magnitud")
plt.xlabel("Frecuencia [Hz]")
plt.ylabel("Ganancia [dB]")
plt.legend()
plt.tight_layout()
plt.show()

plt.figure(figsize=(10,6))
plt.errorbar(frecuencias, fase_deg, yerr=fase_err, fmt='s-', color='orange', capsize=4)
plt.xscale("log")
plt.grid(which='both', linestyle='--', linewidth=0.5)
plt.title("Diagrama de Bode - Fase")
plt.xlabel("Frecuencia [Hz]")
plt.ylabel("Fase [°]")
plt.tight_layout()
plt.show()

osc.write("WGEN:OUTP 0")
osc.close()

print(f"Tiempo transcurrido: {end - start:.4f} segundos")
