#include "../../common.h"

typedef enum {
  MachineTimer_IRQn = 7
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

volatile int svp_simple_015_001_global_var1;
volatile int svp_simple_015_001_global_var2;

void svp_simple_015_001_main() {
  init();
  PLIC_SetPriority(MachineTimer_IRQn, 2);
  PLIC_EnableIRQ(MachineTimer_IRQn);
  __enable_irq();

  int x = rand();
  int y = rand();
  int z;
  int p = rand();

  if ((svp_simple_015_001_global_var1 < y) &&
      (svp_simple_015_001_global_var1 > x))
    z = x + y;

  p == 1 ? svp_simple_015_001_global_var2 : svp_simple_015_001_global_var2;
}

void MachineTimer_IRQHandler() {
  idlerun();
  svp_simple_015_001_global_var1 = 5;
  svp_simple_015_001_global_var2 = 5;
}
