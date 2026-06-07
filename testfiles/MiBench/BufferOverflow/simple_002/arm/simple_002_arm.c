/*
 * BufferOverflow - simple_002
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

#define BUFFER_SIZE 10
typedef unsigned int uint;
int simple_002_global_array[BUFFER_SIZE];
uint simple_002_global_var1;
uint simple_002_global_var2;
void simple_002_Init(void);
int rand(void);

void simple_002_arm_main(void) {
  simple_002_Init();
  if (simple_002_global_var1 < BUFFER_SIZE &&
      simple_002_global_var2 < BUFFER_SIZE) {
    simple_002_global_array[simple_002_global_var1] = 0;
    simple_002_global_array[simple_002_global_var2] = 0;
  }
}

void simple_002_Init(void) {
  simple_002_global_var1 = 0;
  simple_002_global_var2 = 0;
}

void TIM2_IRQHandler(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_002_global_var1 = 0;
    simple_002_global_var2 = rand();
  }
}
