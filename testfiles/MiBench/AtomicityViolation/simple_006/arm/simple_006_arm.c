/*
 * AtomicityViolation - simple_006 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * Shared variable accessed indirectly through helper functions.
 * CPG identifier search in main won't find 'state' directly.
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

volatile int state;

static int get_state(void) { return state; }
static void set_state(int v) { state = v; }

void simple_006_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    int old = get_state();      /* R — indirect read of 'state' */
    int new_val = old + 1;
    set_state(new_val);         /* W — indirect write of 'state' */
                                /* ISR can preempt between R and W */
}

void TIM2_IRQHandler(void) {
    state = 0;                  /* W — direct write of 'state' */
}
