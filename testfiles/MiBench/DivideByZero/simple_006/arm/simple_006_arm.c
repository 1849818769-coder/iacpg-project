/*
 * DivideByZero - simple_006 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * Guard condition (safe_flag) is itself a shared variable.
 * ISR can clear safe_flag, causing __disable_irq() to not execute,
 * then ISR also sets divisor=0 → divide-by-zero.
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
void print(int);

volatile int divisor;
volatile int safe_flag;

void simple_006_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    divisor = 10;
    safe_flag = 1;

    /* ISR can change safe_flag to 0 here → guard doesn't execute */
    if (safe_flag) {
        __disable_irq();
    }

    if (divisor != 0) {
        print(100 / divisor);       /* potential divide-by-zero if unprotected */
    }

    if (safe_flag) {
        __enable_irq();
    }
}

void TIM2_IRQHandler(void) {
    safe_flag = 0;
    divisor = 0;
}
