/*
 * DivideByZero - simple_005 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * Divisor obtained indirectly via get_divisor().
 * Check reads global directly, use reads via function — ISR can
 * change raw_divisor between check and indirect use.
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

volatile int raw_divisor;

static int get_divisor(void) { return raw_divisor; }

void simple_005_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    raw_divisor = 10;

    /* Check: direct read of global */
    if (raw_divisor != 0) {
        /* Use: indirect read via function — ISR can set raw_divisor=0 in between */
        int d = get_divisor();
        print(100 / d);            /* potential divide-by-zero */
    }
}

void TIM2_IRQHandler(void) {
    raw_divisor = 0;
}
