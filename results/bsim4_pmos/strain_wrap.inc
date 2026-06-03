.subckt strain_engine_spice eps_s alpha dvth dmu
.param nu=0.47 beta=1.0 gamma=0.05 beta_r=0.0 gamma_r=0.0
.param tau_m=1e-15 tau_load=1e-12 tau_unload=1e-12
Rmech eps_s eps_s_filt 1
Cmech eps_s_filt 0 {tau_m}
Beps_raw n_eps_t_raw 0 V = '{ (V(eps_s_filt)/2) * (1 - nu + (1 + nu) * cos(2 * V(alpha))) }'
Ghist n_eps_t 0 cur = '{ (V(n_eps_t_raw)-V(n_eps_t)) / ((V(n_eps_t_raw) >= V(n_eps_t)) ? tau_load : tau_unload) }'
Chist n_eps_t 0 1
Bdvth dvth 0 V = '{ -beta * V(n_eps_t) - beta_r * ddt(V(n_eps_t)) }'
Bdmu dmu 0 V = '{ gamma * V(n_eps_t) + gamma_r * ddt(V(n_eps_t)) }'
.ends strain_engine_spice

.subckt bsim4_pmos d g s b
.param W=10u L=180n

.model bsim4_pmos_mod pmos level=54 version=4.4.0
+ vth0=-0.42 u0=150e-4 tox=2.0e-9
+ vfb=-1.0 phi=0.7 k1=0.55
+ wint=0 lint=0 xl=0 xw=0
+ dvt0=1.0 dvt1=2.0 dvt2=-0.032
+ nfactor=1.0 voff=-0.08 eta0=0.08 etab=-0.07
+ cgso=1.0e-10 cgdo=1.0e-10 cgbo=1.0e-10

M1 d g s b bsim4_pmos_mod W={W} L={L}
.ends bsim4_pmos

.subckt strain_aware_device d g s b eps_s alpha
.param nu=0.47 beta=0.8 gamma=0.0 vth0=0.42 mu0=0.015
.param beta_r=0.0 gamma_r=0.0 tau_m=1e-15
.param tau_load=1e-12 tau_unload=1e-12
Xse eps_s alpha dvth dmu strain_engine_spice nu=0.47 beta=0.8 gamma=0.0 beta_r=0.0 gamma_r=0.0 tau_m=1e-15 tau_load=1e-12 tau_unload=1e-12
E_gshift g_eff g dvth 0 -1
Xdev d g_eff s b bsim4_pmos W=10u L=180n
.ends strain_aware_device
