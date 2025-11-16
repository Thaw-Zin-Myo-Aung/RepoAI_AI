package th.ac.mfu.repoai.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import th.ac.mfu.repoai.domain.repositorydto.ContextChunk;
import java.util.List;

@Repository
public interface ContextChunkRepository extends JpaRepository<ContextChunk, Long> {
    List<ContextChunk> findByRepoId(Long repoId);
    List<ContextChunk> findByRepoIdAndCommitSha(Long repoId, String commitSha);
    List<ContextChunk> findByChunkIdIn(List<Long> chunkIds);
}
