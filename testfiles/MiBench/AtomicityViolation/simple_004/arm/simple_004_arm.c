/*
 * atomicityViolation - simple_001
 * Architecture: ARM (Cortex-M / CMSIS)
 */

#include <stdint.h>

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

void init(void);
void idlerun(void);

volatile int global_var1;
volatile int global_var2;

void simple_001_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    int x = rand();
    int y = rand();
    int z;
    int p = rand();

    if ((global_var1 < y) && (global_var1 > x))
        z = x + y;

    p == 1 ? global_var2 : global_var2;
}

void TIM2_IRQHandler(void) {
    idlerun();
    global_var1 = 5;
    global_var2 = 5;
}
