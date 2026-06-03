simulator lang=spectre
subckt strain_demo_mos d g s b
  parameters kp=2e-4 vth=0.35 lambda=0.02
  Id1 (d s) bsource i = kp*max(0, v(g)-v(s)-vth)*(1+lambda*max(0, v(d)-v(s)))
ends strain_demo_mos

simulator lang=spectre
ahdl_include "strain_engine.va"
subckt strain_aware_device d g s b eps_s alpha
  parameters nu=0.47 beta=0.6 gamma=0.0 vth0=0.35 mu0=0.02
  parameters beta_r=0.0 gamma_r=0.0 tau_m=1e-15
  parameters tau_load=1e-12 tau_unload=1e-12
  Xse (eps_s alpha dvth dmu) strain_engine nu=0.47 beta=0.6 gamma=0.0 beta_r=0.0 gamma_r=0.0 tau_m=1e-15 tau_load=1e-12 tau_unload=1e-12
  E_gshift (g_eff g) vsource v = -v(dvth)
  Xdev (d g_eff s b) strain_demo_mos kp=2e-4 vth=0.35
ends strain_aware_device
