'''
Author: jianzhnie
Date: 2022-01-05 16:21:54
LastEditTime: 2022-01-05 17:53:46
LastEditors: jianzhnie
Description:

'''

import sys

import torch
import torch.optim as optim
from tqdm.auto import tqdm

from nlptoolkit.data.datasets.nlmdataset import GloveDataset
from nlptoolkit.data.utils.utils import (get_loader, load_reuters,
                                         save_pretrained)
from nlptoolkit.models.word2vec.glove import GloveModel

sys.path.append('../../')

if __name__ == '__main__':

    embedding_dim = 64
    context_size = 2
    batch_size = 1024
    num_epoch = 10

    # 用以控制样本权重的超参数
    m_max = 100
    alpha = 0.75
    # 从文本数据中构建GloVe训练数据集
    corpus, vocab = load_reuters()
    dataset = GloveDataset(corpus, vocab, context_size=context_size)
    data_loader = get_loader(dataset, batch_size)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = GloveModel(len(vocab), embedding_dim)
    model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    model.train()
    for epoch in range(num_epoch):
        total_loss = 0
        for batch in tqdm(data_loader, desc=f'Training Epoch {epoch}'):
            # words, contexts, counts 的 shape : batch_size * 1
            words, contexts, counts = [x.to(device) for x in batch]
            # 提取batch内词、上下文的向量表示及偏置
            # word_embeds: Batch_size * Embedding_dim
            # word_biases: Batch_size * 1
            word_embeds, word_biases = model.forward_w(words)
            # context_embeds: Batch_size * Embedding_dim
            # context_biases: Batch_size * 1
            context_embeds, context_biases = model.forward_c(contexts)
            # 回归目标值：必要时可以使用log(counts+1)进行平滑
            log_counts = torch.log(counts)
            # 样本权重
            weight_factor = torch.clamp(torch.pow(counts / m_max, alpha),
                                        max=1.0)
            optimizer.zero_grad()
            # 计算batch内每个样本的L2损失
            loss = (torch.sum(word_embeds * context_embeds, dim=1) +
                    word_biases + context_biases - log_counts)**2
            # 样本加权损失
            wavg_loss = (weight_factor * loss).mean()
            wavg_loss.backward()
            optimizer.step()
            total_loss += wavg_loss.item()
        print(f'Loss: {total_loss:.2f}')

    # 合并词嵌入矩阵与上下文嵌入矩阵，作为最终的预训练词向量
    combined_embeds = model.w_embeddings.weight + model.c_embeddings.weight
    save_pretrained(vocab, combined_embeds.data, 'glove.vec')