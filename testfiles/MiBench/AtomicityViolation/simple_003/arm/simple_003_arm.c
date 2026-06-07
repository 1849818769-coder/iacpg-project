#include "../../common.h"

typedef enum {
  DMA1_Channel1_IRQn = 11
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void NVIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

volatile int svp_simple_008_001_global_var;
volatile int svp_simple_008_001_global_array[100];
volatile int svp_simple_008_001_global_out = 0;

void svp_simple_008_001_func_1();

void svp_simple_008_001_main() {
  init();
  NVIC_SetPriority(DMA1_Channel1_IRQn, 2);
  NVIC_EnableIRQ(DMA1_Channel1_IRQn);
  __enable_irq();
  int p = 1;
  int q = 2;

  svp_simple_008_001_global_array[p + q] = 0x09;
  svp_simple_008_001_global_array[40] = 0x01;
  svp_simple_008_001_func_1();
}

void svp_simple_008_001_func_1() {
  int reader1, reader2;
  int i = 1;
  int j = 2;
  int p = 1;
  int q = 3;
  reader1 = svp_simple_008_001_global_array[i * 20 + j * 10];
  reader2 = svp_simple_008_001_global_array[p + q];

  /* Use the readers: ISR may overwrite array between main's writes and
     func_1's reads, causing unexpected values (W-W-R atomicity violation) */
  svp_simple_008_001_global_out = reader1 + reader2;
}

void DMA1_Channel1_IRQHandler() {
  for (int k = 0; k < 100; k++)
    svp_simple_008_001_global_array[k] = 0x05;
}
