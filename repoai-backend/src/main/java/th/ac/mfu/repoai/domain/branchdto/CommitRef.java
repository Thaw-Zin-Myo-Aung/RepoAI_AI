package th.ac.mfu.repoai.domain.branchdto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record CommitRef(String sha, String url) {
}
