/*
 * multiwordDatarace - simple_002
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

volatile uint64_t curr_sec = 0;
volatile uint32_t sec_high = 1;
volatile uint32_t sec_low = 2;
volatile uint64_t front_sec = 0;

void simple_002_arm_main(void) {
    init();
    idlerun();
    front_sec = curr_sec;
}

void TIM2_IRQHandler(void) {
    curr_sec = ((uint64_t)sec_high << 32) | sec_low;
}
