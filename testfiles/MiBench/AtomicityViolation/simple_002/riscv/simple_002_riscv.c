#include "../../common.h"

typedef enum {
  MachineSoftware_IRQn = 3,
  MachineExternal_IRQn = 11
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

volatile int svp_simple_004_001_condition1 = 1;
volatile int svp_simple_004_001_condition2 = 1;
volatile int svp_simple_004_001_condition3 = 1;
volatile int svp_simple_004_001_condition4 = 1;
volatile int svp_simple_004_001_condition5 = 1;
volatile int svp_simple_004_001_condition6 = 1;

volatile int svp_simple_004_001_global_var1 = 0x11;
volatile int svp_simple_004_001_global_var2 = 0x22;
volatile int svp_simple_004_001_global_var3 = 0x33;
volatile int svp_simple_004_001_global_out = 0;

void svp_simple_004_001_main() {
  init();
  PLIC_SetPriority(MachineSoftware_IRQn, 1);
  PLIC_SetPriority(MachineExternal_IRQn, 2);
  PLIC_DisableIRQ(MachineExternal_IRQn);
  __enable_irq();

  int reader1, reader2;
  int reader3, reader4;
  int reader5, reader6;

  if (svp_simple_004_001_condition1 == 1) {
    reader1 = svp_simple_004_001_global_var1;
    reader5 = svp_simple_004_001_global_var3;
  }

  if (svp_simple_004_001_condition2 == 1) {
    reader2 = svp_simple_004_001_global_var1;
    reader6 = svp_simple_004_001_global_var3;
  }

  if (svp_simple_004_001_condition4 == 1)
    reader3 = svp_simple_004_001_global_var2;

  if (svp_simple_004_001_condition5 == 1)
    reader4 = svp_simple_004_001_global_var2;

  /* Use the readers: inconsistent values between reader1 and reader2
     indicate an atomicity violation (R-W-R on global_var1) */
  svp_simple_004_001_global_out = reader1 + reader2 + reader3 + reader4 + reader5 + reader6;
}

void MachineSoftware_IRQHandler() {
  svp_simple_004_001_condition6 = 0;

  if (svp_simple_004_001_condition3 == 1)
    svp_simple_004_001_global_var1 = 0xaa;
  else
    svp_simple_004_001_global_var3 = 0xcc;

  PLIC_EnableIRQ(MachineExternal_IRQn);
}

void MachineExternal_IRQHandler() {
  if (svp_simple_004_001_condition6 == 1)
    svp_simple_004_001_global_var2 = 0x22;
}
