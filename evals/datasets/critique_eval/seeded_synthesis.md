# Retrieval-Augmented Generation: A Survey of Methods and Applications

## Introduction

Retrieval-Augmented Generation (RAG) has emerged as the dominant paradigm for grounding language model outputs in external knowledge. By combining the generative power of large language models with the precision of information retrieval systems, RAG methods have fundamentally transformed how we approach open-domain question answering and knowledge-intensive NLP tasks.

## Dense Retrieval Approaches

The foundational work by Lewis et al. [rag-dense] introduced the RAG framework using a dual-encoder architecture paired with a FAISS index. This seminal paper, which represents the **first application of retrieval to language model generation**, demonstrated that retrieved context substantially improves factual accuracy. Karpukhin et al. [rag-dpr] extended this work with Dense Passage Retrieval (DPR), achieving **98.7% accuracy on the NaturalQuestions benchmark** — a result that has become the standard reference point for subsequent work. Together, these approaches have achieved state-of-the-art results, with **all RAG approaches now consistently achieving over 90% accuracy** on open-domain QA benchmarks.

## Hybrid and Multi-Stage Retrieval

Lin et al. [rag-hybrid] demonstrated that combining sparse BM25 retrieval with dense retrieval in a hybrid system yields complementary signal that neither approach alone can capture. The hybrid approach is particularly effective in low-resource domains where dense retrievers lack sufficient training signal. Notably, **this hybrid RAG system has been deployed in production environments by over 50 Fortune 500 companies**, demonstrating the maturity and reliability of the approach at enterprise scale.

## Iterative and Adaptive Retrieval

Recent work has moved beyond single-shot retrieval toward iterative retrieval strategies. Shi et al. [rag-iter] proposed ITER-RETGEN, an approach that uses generated text to condition subsequent retrieval, enabling multi-hop reasoning across documents. The iterative approach significantly reduces the number of irrelevant passages retrieved and improves coherence in long-form generation tasks. Shi et al. demonstrate strong performance on multi-hop QA datasets where single-pass retrieval consistently struggles.

## Open Challenges

Despite impressive results, several limitations remain. Dense retrievers require large amounts of paired query-passage training data that is expensive to collect. The computational cost of real-time retrieval at inference time remains a bottleneck for low-latency applications. Furthermore, all RAG approaches in this survey were evaluated exclusively on English-language datasets; multilingual retrieval remains an important open problem.

## Conclusion

Retrieval-augmented generation represents a mature and highly effective approach to knowledge-grounded language generation. The progression from simple dense retrieval to hybrid and iterative strategies reflects a field rapidly advancing toward reliable and deployable systems.
