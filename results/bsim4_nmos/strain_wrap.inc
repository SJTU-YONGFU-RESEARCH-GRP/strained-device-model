.subckt strain_engine_spice eps_s alpha dvth dmu
.param nu=0.47 beta=1.0 gamma=0.05
Beps_t n_eps_t 0 V = '{ (V(eps_s)/2) * (1 - nu + (1 + nu) * cos(2 * V(alpha))) }'
Bdvth dvth 0 V = '{ -beta * V(n_eps_t) }'
Bdmu dmu 0 V = '{ gamma * V(n_eps_t) }'
.ends strain_engine_spice

.subckt bsim4_nmos d g s b
.param W=10u L=180n

.model bsim4_nmos_mod nmos level=54 version=4.4.0
+ vth0=0.40 u0=400e-4 tox=2.0e-9
+ vfb=-1.0 phi=0.7 k1=0.53
+ wint=0 lint=0 xl=0 xw=0
+ dvt0=1.0 dvt1=2.0 dvt2=-0.032
+ nfactor=1.0 voff=-0.08 eta0=0.08 etab=-0.07
+ cgso=1.0e-10 cgdo=1.0e-10 cgbo=1.0e-10

M1 d g s b bsim4_nmos_mod W={W} L={L}
.ends bsim4_nmos

.subckt strain_aware_device d g s b eps_s alpha
.param nu=0.47 beta=0.8 gamma=0.0 vth0=0.4 mu0=0.04
Xse eps_s alpha dvth dmu strain_engine_spice nu=nu beta=beta gamma=gamma
E_gshift g_eff g dvth 0 -1
Xdev d g_eff s b bsim4_nmos W=10u L=180n
.ends strain_aware_device
