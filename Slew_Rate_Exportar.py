# -*- coding: utf-8 -*-
"""
Medida experimental del Slew Rate
Versión: Oct 2025
Autores: alexr y mbuetas (modificado)
"""

import numpy as np
import matplotlib.pyplot as plt
import pyvisa
import time


FREQ_SR = 1500000         
VIN_INICIAL = 0.5        
VIN_FINAL = 5.0         
PASO_VIN = 0.5           
N_MEDIDAS = 10              
ARCHIVO_SALIDA = r"slew_rate_mediciones.txt"


rm = pyvisa.ResourceManager()
print("Recursos disponibles:", rm.list_resources())

osc = rm.open_resource("visa://155.210.95.41/USB0::0x0957::0x179B::MY50512084::INSTR")
osc.write_termination = '\n'
osc.read_termination = '\n'

osc.write("WGEN:FUNC STEP")
osc.write(f"WGEN:FREQ {FREQ_SR}")
osc.write("WGEN:VOLT:OFFS 0")
osc.write("WGEN:OUTP 1")
osc.write("CHAN1:VOLT:OFFS 0")
osc.write("CHAN2:VOLT:OFFS 0")
osc.write(":ACQuire:TYPE AVER")


def ajustar_escalas_SR(f, vin):
    """Ajusta el timebase y escala de tensión del osciloscopio para SR."""
    time_scale = 1 / (10 * f)
    osc.write(f"TIM:SCAL {time_scale}")
    volt_scale = vin / 3
    osc.write(f"CHAN2:SCALe {volt_scale}")

def medir_SR(vin):
    sr_values = []
    osc.write(f"WGEN:VOLT {vin}")
    ajustar_escalas_SR(FREQ_SR, vin)
    time.sleep(0.5)

    for _ in range(N_MEDIDAS):
        try:
            osc.write(":MEAS:RIS CHAN2")
            t_rise = float(osc.query(":MEAS:RIS?"))
            osc.write(":MEAS:VPP CHAN2")
            Vpp = float(osc.query(":MEAS:VPP?"))
            SR_measured = (0.8 * Vpp) / t_rise / 1e6  # [V/µs]
            sr_values.append(SR_measured)
            time.sleep(0.2)
        except pyvisa.errors.VisaIOError:
            sr_values.append(np.nan)
    return sr_values



niveles_vin = np.arange(VIN_INICIAL, VIN_FINAL + PASO_VIN, PASO_VIN)
SR_medias = []
SR_std = []

for vin in niveles_vin:
    sr_vals = medir_SR(vin)
    sr_vals = np.array(sr_vals)
    sr_mean = np.nanmean(sr_vals)
    sr_sigma = np.nanstd(sr_vals, ddof=1)
    SR_medias.append(sr_mean)
    SR_std.append(sr_sigma)
    print(f"VIN={vin:.2f} Vpp → SR = {sr_mean:.2f} ± {sr_sigma:.2f} V/µs")


with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
    f.write("VIN(Vpp)\tSR(V/us)\tDesv(V/us)\n")
    for v, sr, err in zip(niveles_vin, SR_medias, SR_std):
        f.write(f"{v:.3f}\t{sr:.6f}\t{err:.6f}\n")


plt.figure(figsize=(8,6))
plt.errorbar(niveles_vin, SR_medias, yerr=SR_std, fmt='o-', capsize=5)
plt.title("Slew Rate vs Amplitud de Entrada")
plt.xlabel("Amplitud de Entrada VIN [Vpp]")
plt.ylabel("Slew Rate [V/µs]")
plt.grid(True, linestyle='--', linewidth=0.5)
plt.tight_layout()
plt.show()


osc.write("WGEN:OUTP 0")
osc.close()

