import numpy as np
import pyvisa
import time
import matplotlib.pyplot as plt

start = time.time()


FREQ_FIJA = 5000        
VIN_INICIAL = 0.5    
VIN_FINAL = 8.0       
PASO_VIN = 0.25        
N_MEDIDAS = 3            


rm = pyvisa.ResourceManager()
print("Recursos disponibles:", rm.list_resources())

osc = rm.open_resource("visa://155.210.95.41/USB0::0x0957::0x179B::MY50512084::INSTR")
osc.write_termination = '\n'
osc.read_termination = '\n'
osc.timeout = 10000


osc.write(":WGEN:FUNC SIN")                     
osc.write(f":WGEN:FREQ {FREQ_FIJA}")             
osc.write(f":WGEN:VOLT {VIN_INICIAL}")           
osc.write(":WGEN:VOLT:OFFS 0")                   
osc.write(":WGEN:OUTP ON")                       

# Osciloscopio
osc.write(":CHAN1:DISP ON")
osc.write("CHAN1:VOLT:OFFS 0")
osc.write(":ACQuire:TYPE AVER")


time_scale = 3 / (10 * FREQ_FIJA)
osc.write(f"TIM:SCAL {time_scale}")


def ajustar_escala_volt(volt):
    volt_scale = max(volt / 3, 0.1)
    osc.write(f"CHAN2:SCAL {volt_scale}")
    osc.write("CHAN2:VOLT:OFFS 0")

def medir_vin():
    try:
        osc.write(":MEAS:VPP CHAN2")
        return float(osc.query(":MEAS:VPP? CHAN2"))
    except pyvisa.errors.VisaIOError:
        return np.nan

valores_generador = np.arange(VIN_INICIAL, VIN_FINAL + PASO_VIN, PASO_VIN)
vin_medido = []

for vgen in valores_generador:
    print(f"\n Ajustando generador a {vgen:.2f} Vpp")

    osc.write(f":WGEN:VOLT {vgen}")
    time.sleep(0.5)

    ajustar_escala_volt(vgen)
    time.sleep(0.3)

    medidas = []
    for _ in range(N_MEDIDAS):
        v1 = medir_vin()
        if not np.isnan(v1):
            medidas.append(v1)
        time.sleep(0.2)

    if medidas:
        vin_prom = np.mean(medidas)
    else:
        vin_prom = np.nan

    vin_medido.append(vin_prom)
    print(f"Vin medido = {vin_prom:.3f} Vpp")


ruta = r"C:\Users\alexr\OneDrive\Desktop\Máster Física Y Tecnologías Físicas\Primer Cuatri\Instrumentación Inteligente\Codigo\txt\Vin_Vcc.txt"
with open(ruta, "w", encoding="utf-8") as file:
    file.write("Vgen(Vpp)\tVin_medido(Vpp)\n")
    for vgen, vmed in zip(valores_generador, vin_medido):
        file.write(f"{vgen:.3f}\t{vmed:.6f}\n")


plt.figure(figsize=(8,6))
plt.plot(valores_generador, vin_medido, 'o-', label="Vin medido (CH1)")
plt.title("Vout medido vs Voltaje del generador (5 kHz)")
plt.xlabel("Voltaje del generador [Vpp]")
plt.ylabel("Vout medido (CH2) [Vpp]")
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()
plt.tight_layout()
plt.show()


osc.write(":WGEN:OUTP OFF")
osc.close()

end = time.time()
print(f"\nTiempo total: {end - start:.2f} s")

