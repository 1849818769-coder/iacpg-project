/*
 * DivideByZero - simple_002
 * Architecture: ARM (Cortex-M / CMSIS)
 */

#include <stdint.h>

typedef enum {
  TIM2_IRQn = 28,
  USART1_IRQn = 31
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void NVIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

int rand(void);

volatile int simple_002_x, simple_002_y, simple_002_z;

void simple_002_arm_main(void) {
    simple_002_x = rand();
    simple_002_y = rand();
    if (simple_002_x < simple_002_y) {
        simple_002_z = 1 / (simple_002_x - simple_002_y);
    }
}

void TIM2_IRQHandler(void) {
    simple_002_x++;
    simple_002_y--;
}

void USART1_IRQHandler(void) {
    simple_002_x++;
    simple_002_y--;
    if (simple_002_x == simple_002_y) {
        simple_002_x++;
        simple_002_y--;
    }
}
