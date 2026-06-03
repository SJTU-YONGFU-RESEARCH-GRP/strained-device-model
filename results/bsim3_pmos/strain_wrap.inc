.subckt strain_engine_spice eps_s alpha dvth dmu
.param nu=0.47 beta=1.0 gamma=0.05
Beps_t n_eps_t 0 V = '{ (V(eps_s)/2) * (1 - nu + (1 + nu) * cos(2 * V(alpha))) }'
Bdvth dvth 0 V = '{ -beta * V(n_eps_t) }'
Bdmu dmu 0 V = '{ gamma * V(n_eps_t) }'
.ends strain_engine_spice

.subckt bsim3_pmos d g s b
.param W=10u L=180n

.model bsim3_pmos_mod pmos level=8 version=3.3.0
+ vth0=-0.42 u0=150e-4 tox=4.0e-9 nsub=5.0e16
+ vfb0=-1.0 phi=0.7 k1=0.55 k2=0.02
+ voff=-0.08 nfactor=1.0 eta0=0.08 etab=-0.07
+ wint=0 lint=0 xl=0 xw=0
+ cgso=1.0e-10 cgdo=1.0e-10 cgbo=1.0e-10

M1 d g s b bsim3_pmos_mod W={W} L={L}
.ends bsim3_pmos

.subckt strain_aware_device d g s b eps_s alpha
.param nu=0.47 beta=0.8 gamma=0.0 vth0=0.42 mu0=0.015
Xse eps_s alpha dvth dmu strain_engine_spice nu=nu beta=beta gamma=gamma
E_gshift g_eff g dvth 0 -1
Xdev d g_eff s b bsim3_pmos W=10u L=180n
.ends strain_aware_device
