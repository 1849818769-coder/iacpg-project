#include "../../common.h"

typedef enum {
  TIM2_IRQn = 28
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void NVIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

volatile int svp_simple_015_001_global_var1;
volatile int svp_simple_015_001_global_var2;

void svp_simple_015_001_main() {
  init();
  NVIC_SetPriority(TIM2_IRQn, 2);
  NVIC_EnableIRQ(TIM2_IRQn);
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

void TIM2_IRQHandler() {
  idlerun();
  svp_simple_015_001_global_var1 = 5;
  svp_simple_015_001_global_var2 = 5;
}
