/*
 * MultiwordDataRace - simple_005 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * ISR uses non-standard name 'system_tick_callback' instead of *IRQHandler.
 * CPG naming pattern match will fail to identify it as ISR.
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

volatile int64_t timestamp;

void simple_005_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    /* Non-atomic 64-bit read on 32-bit ARM */
    int64_t snap = timestamp;
    if (snap > 0) {
        idlerun();
    }
}

/* Non-standard ISR name — registered via vector table, not by naming convention */
void system_tick_callback(void) {
    timestamp = timestamp + 1;      /* Non-atomic 64-bit read-modify-write */
}
