package th.ac.mfu.repoai.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import th.ac.mfu.repoai.domain.BranchEntity;

import java.util.List;
import java.util.Optional;

@Repository
public interface BranchRepository extends JpaRepository<BranchEntity, Long> {

    List<BranchEntity> findByRepoIdOrderByNameAsc(Long repoId);

    Optional<BranchEntity> findByRepoIdAndName(Long repoId, String name);

    boolean existsByRepoIdAndName(Long repoId, String name);

    // For cleanup: delete branches that are no longer present on GitHub
    Long deleteByRepoIdAndNameNotIn(Long repoId, List<String> names);
}
