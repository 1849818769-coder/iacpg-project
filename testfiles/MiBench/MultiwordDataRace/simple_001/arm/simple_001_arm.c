/*
 * multiwordDatarace - simple_001
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

volatile int64_t down_counter_ms = 0;

void simple_001_arm_main(void) {
    __disable_irq();
    init();
    __enable_irq();
    down_counter_ms = 500;
    idlerun();
}

void TIM2_IRQHandler(void) {
    down_counter_ms = down_counter_ms - 1;
}
