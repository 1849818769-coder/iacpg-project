/*
 * BufferOverflow - simple_006 (hard, TN)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * True protection: __disable_irq() fully covers the check-use window.
 * No real defect — tests whether tools correctly identify as safe.
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

#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int idx;

void simple_006_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    /* Full protection around check-use */
    __disable_irq();
    if (idx < BUFFER_SIZE) {
        buffer[idx] = 99;          /* safe: global IRQ disabled */
    }
    __enable_irq();
}

void TIM2_IRQHandler(void) {
    idx = BUFFER_SIZE + 1;
}
