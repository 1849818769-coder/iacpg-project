/*
 * MultiwordDataRace - simple_006 (hard)
 * Architecture: ARM (Cortex-M / CMSIS)
 *
 * Struct with two 32-bit fields read non-atomically.
 * Each field is individually atomic on 32-bit ARM, but the pair
 * requires consistency — ISR can modify between R1(x) and R2(y).
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

typedef struct {
    volatile int32_t x;
    volatile int32_t y;
} coord_t;

coord_t position;

void simple_006_arm_main(void) {
    init();
    NVIC_SetPriority(TIM2_IRQn, 2);
    NVIC_EnableIRQ(TIM2_IRQn);
    __enable_irq();

    /* Non-atomic compound read: ISR can modify between R1 and R2 */
    int32_t px = position.x;        /* R1 */
    int32_t py = position.y;        /* R2 */
    int32_t dist = px * px + py * py;
    (void)dist;
}

void TIM2_IRQHandler(void) {
    position.x = position.x + 1;
    position.y = position.y + 1;
}
