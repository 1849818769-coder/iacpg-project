/*
 * AtomicityViolation - simple_005 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * Difficulty: Selective masking + priority nesting.
 * Main disables TIM2 (low-priority) around critical section,
 * but USART1 (high-priority) is NOT disabled and can still preempt.
 * CPG sees NVIC_DisableIRQ and may conclude "protected".
 */

#include <stdint.h>

typedef enum {
  TIM2_IRQn = 28,
  USART1_IRQn = 37
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
int rand(void);

volatile int shared_counter;

void simple_005_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 3);
    NVIC_SetPriority(USART1_IRQn, 1);
    NVIC_EnableIRQ(TIM2_IRQn);
    NVIC_EnableIRQ(USART1_IRQn);
    __enable_irq();

    /* Selectively disable only TIM2 (low-priority) */
    NVIC_DisableIRQ(TIM2_IRQn);

    int tmp = shared_counter;       /* R1 */
    tmp = tmp + 1;
    shared_counter = tmp;           /* W1 — USART1 can preempt between R1 and W1 */

    NVIC_EnableIRQ(TIM2_IRQn);
}

void TIM2_IRQHandler(void) {
    /* This ISR is disabled during critical section — cannot preempt */
    shared_counter = 0;
}

void USART1_IRQHandler(void) {
    /* High-priority, NOT disabled — can preempt during R1-W1 window */
    shared_counter = shared_counter + 10;
}
