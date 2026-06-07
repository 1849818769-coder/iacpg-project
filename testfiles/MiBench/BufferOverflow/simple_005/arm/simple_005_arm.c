/*
 * BufferOverflow - simple_005 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * Deceptive guard: __disable_irq() protects initialization only,
 * NOT the array access. CPG sees disable call and may conclude "safe".
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
volatile unsigned int index_val;

void simple_005_arm_main(void) {
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);

    /* Guard covers initialization ONLY */
    __disable_irq();
    index_val = 0;
    __enable_irq();

    /* No protection here — ISR can change index_val between check and use */
    if (index_val < BUFFER_SIZE) {
        buffer[index_val] = 42;     /* potential OOB */
    }
}

void TIM2_IRQHandler(void) {
    index_val = BUFFER_SIZE + 5;    /* out-of-bounds value */
}
